#!/usr/bin/env python3
"""kwx_sizing.py -- bet-sizing optimizer for the K-WX weather-nowcast edge on a small bankroll.

Answers: on a $BANKROLL account, how many contracts per fire (as a fraction of Kelly, with what caps)
MAXIMIZES growth while MINIMIZING risk of a bad drawdown/ruin -- using the REAL per-fire outcomes
(including the actual -1.0/-0.77 losses), not a Gaussian approximation.

Why not just full Kelly: the per-fire loss probability is tiny (~0.35%) so naive Kelly says stake ~98% of
bankroll on ONE fire -- which is ruinous, because if that fire is one of the rare losers you lose most of
the account. The real risk here is CONCENTRATION, not per-bet variance. So we sweep fractional-Kelly x
per-fire cap x per-city-day cap and score each on median growth AND downside (5th pct, max drawdown, prob
of net loss, prob of ruin), then report the frontier.

Realism baked in: integer contracts (Kalshi min 1), quadratic fees, a LATENCY HAIRCUT (price/PnL taken at
the gap `--latency` minutes after the cross, since live we act at ~2-5 min not 0), per-city daily cap, and
intraday settlement (a day's fires settle together at day end -> no intraday compounding).

Usage:
  python kwx_sizing.py                 # sweep, $50 bankroll, 3-min latency, print frontier + recommendation
  python kwx_sizing.py --bankroll 50 --latency 3 --days 60 --trials 4000
"""
import json, os, math, argparse, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_trackA_results_raw.json")
DEPTH_CAP = 25          # max contracts fillable per fire (Tier-1: books thin; won't bind at $50 anyway)
WINP = 0.9965           # empirical deployable win prob (Track A) -- used for the Kelly fraction


def kalshi_fee(price):
    return math.ceil(0.07 * price * (1 - price) * 100) / 100.0


def load_fires(latency_min):
    """Return list of fires: {date, city, price, outcome(0/1), pnl_per_ct} at the chosen action latency."""
    raw = json.load(open(RAW))
    k = str(latency_min)
    fires = []
    for rec in raw:
        c = rec["cells"].get("1_3")
        if not c or not c.get("fired") or c["exec_price"] >= 0.99:
            continue
        outcome = c.get("outcome")
        if outcome is None:
            outcome = 1 if c["pnl"] > 0 else 0
        gap = c.get("decay_gap_by_min", {}).get(k)
        price = (1.0 - gap) if gap is not None else c["exec_price"]
        price = min(0.99, max(0.01, price))
        if price >= 0.99:
            continue  # gap fully closed at this latency -> not tradeable
        pnl = outcome - price - kalshi_fee(price)   # per-contract $ at this latency
        fires.append({"date": rec["date"], "city": rec.get("city", "?"),
                      "price": price, "outcome": outcome, "pnl": pnl})
    return fires


def kelly_fraction(price, p=WINP):
    """Fraction of bankroll to STAKE on a binary contract at `price` (full Kelly). b = (1-c)/c net odds,
    lose full stake with prob q. f* = p - q/b = p - q*c/(1-c)."""
    q = 1 - p
    b = (1 - price) / price
    return max(0.0, p - q / b)


def simulate(fires_by_day, day_keys, rule, bankroll0, days, trials, seed=12345,
             unfillable=0.21, baddays_prob=0.0):
    """Monte Carlo: each trial bootstraps `days` fire-days (with replacement) and evolves the bankroll.
    rule = dict(lam, per_fire_cap, per_city_cap).
    unfillable: fraction of fires with NO executable book at fire time (Tier-1: ~21%) -> skipped.
    baddays_prob: prob a day is a synthetic 'heat-dome contagion' day where EVERY fire loses (-price) --
      a stressor for the correlated tail the 65-day history is too clean to show. Returns metrics."""
    rng = random.Random(seed)
    finals, mdds, ruined, netloss = [], [], 0, 0
    RUIN = bankroll0 * 0.2
    for _ in range(trials):
        bank = bankroll0
        peak = bank
        mdd = 0.0
        ruin_hit = False
        for _d in range(days):
            day = rng.choice(day_keys)
            fires = fires_by_day[day]
            bad_day = rng.random() < baddays_prob
            city_spent = defaultdict(float)
            day_pnl = 0.0
            avail = bank
            # process fires cheapest-price-first (biggest gap -> best EV first)
            for f in sorted(fires, key=lambda x: x["price"]):
                if rng.random() < unfillable:      # no book at fire time -> cannot execute
                    continue
                price = f["price"]
                fk = kelly_fraction(price)
                stake_frac = min(rule["lam"] * fk, rule["per_fire_cap"])
                budget = stake_frac * bank
                room_city = rule["per_city_cap"] * bank - city_spent[f["city"]]
                budget = min(budget, room_city, avail)
                if budget <= 0:
                    continue
                n = int(budget / price)          # integer contracts
                n = min(n, DEPTH_CAP)
                if n < 1:
                    continue
                cost = n * price
                city_spent[f["city"]] += cost
                avail -= cost
                pnl_ct = (-price - kalshi_fee(price)) if bad_day else f["pnl"]  # bad day -> full loss
                day_pnl += n * pnl_ct
            bank += day_pnl
            peak = max(peak, bank)
            mdd = max(mdd, (peak - bank) / peak if peak > 0 else 0)
            if bank <= RUIN:
                ruin_hit = True
        finals.append(bank)
        mdds.append(mdd)
        ruined += 1 if ruin_hit else 0
        netloss += 1 if bank < bankroll0 else 0
    finals.sort()
    n = len(finals)
    return {
        "median_final": finals[n // 2],
        "p5_final": finals[max(0, n // 20)],
        "p95_final": finals[min(n - 1, n - n // 20)],
        "mean_final": sum(finals) / n,
        "median_mdd": sorted(mdds)[len(mdds) // 2],
        "worst_mdd": max(mdds),
        "prob_ruin": ruined / trials,
        "prob_netloss": netloss / trials,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bankroll", type=float, default=50.0)
    ap.add_argument("--latency", type=int, default=3, choices=[0, 1, 2, 5, 10, 30, 60])
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--unfillable", type=float, default=0.21)   # Tier-1: ~21% empty books at fire time
    ap.add_argument("--baddays", type=float, default=0.02)      # synthetic heat-dome contagion day prob
    args = ap.parse_args()

    fires = load_fires(args.latency)
    by_day = defaultdict(list)
    for f in fires:
        by_day[f["date"]].append(f)
    day_keys = list(by_day)
    daily_ct = sum(len(v) for v in by_day.values()) / len(by_day)
    print(f"K-WX sizing sim | bankroll ${args.bankroll:.0f} | action latency {args.latency}min | "
          f"{len(fires)} fires / {len(day_keys)} days (~{daily_ct:.0f} fires/day) | "
          f"{args.days}-day runs x {args.trials} trials")
    print(f"per-fire mean price {sum(f['price'] for f in fires)/len(fires):.3f}, "
          f"mean pnl/ct +{sum(f['pnl'] for f in fires)/len(fires):.4f} (after {args.latency}min haircut)\n")

    print(f"realism: {args.unfillable:.0%} unfillable (empty book), {args.baddays:.0%}/day synthetic "
          f"heat-dome contagion (all fires lose)\n")
    grid = []
    for lam in (0.05, 0.10, 0.25, 0.50, 1.00):
        for pf in (0.05, 0.10, 0.20, 0.40):
            rule = {"lam": lam, "per_fire_cap": pf, "per_city_cap": 0.175}
            m = simulate(by_day, day_keys, rule, args.bankroll, args.days, args.trials,
                         unfillable=args.unfillable, baddays_prob=args.baddays)
            grid.append((lam, pf, m))

    print(f"{'Kelly-frac':>10}{'perFireCap':>11}{'medFinal':>10}{'p5':>8}{'p95':>9}"
          f"{'medMDD':>8}{'ruin%':>7}{'netLoss%':>9}")
    for lam, pf, m in grid:
        print(f"{lam:>10.2f}{pf:>11.0%}{m['median_final']:>10.2f}{m['p5_final']:>8.2f}"
              f"{m['p95_final']:>9.2f}{m['median_mdd']:>7.0%}{m['prob_ruin']*100:>7.1f}{m['prob_netloss']*100:>9.1f}")

    # recommendation: maximize median growth subject to prob_ruin<1% and p5>=bankroll (no net loss at 5th pct)
    safe = [(lam, pf, m) for lam, pf, m in grid if m["prob_ruin"] < 0.01 and m["p5_final"] >= args.bankroll]
    if safe:
        best = max(safe, key=lambda x: x[2]["median_final"])
        lam, pf, m = best
        growth = (m["median_final"] / args.bankroll) ** (1 / args.days) - 1
        print(f"\nRECOMMENDED (max growth s.t. ruin<1% and 5th-pct>=start): "
              f"Kelly-frac={lam:.2f}, per-fire cap={pf:.0%}, per-city cap=17.5%")
        print(f"  -> median ${args.bankroll:.0f} -> ${m['median_final']:.2f} over {args.days} days "
              f"(~{growth*100:.2f}%/day median), p5 ${m['p5_final']:.2f}, ruin {m['prob_ruin']*100:.1f}%")
    else:
        print("\nNo rule met ruin<1% AND p5>=start -- tighten caps / lower Kelly fraction.")


if __name__ == "__main__":
    main()
