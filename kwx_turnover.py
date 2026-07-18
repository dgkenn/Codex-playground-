#!/usr/bin/env python3
"""kwx_turnover.py -- does SELLING winners early (freeing capital) raise DAILY RETURN on a small bankroll?

On a capital-constrained bankroll, fires spread across the afternoon (US timezones) compete for capital. If
we HOLD to evening settlement, capital is locked all day -> few concurrent fires. If we SELL at ~99c (~14 min
after entry, 89% of winners converge), capital recycles -> more fires/day -> potentially higher daily return
DESPITE ~3c/ct lower per-fire EV. This intraday sim (real t_star fire times + real convergence times + real
outcomes) measures the daily-return difference, HOLD vs SELL99, across bankrolls.

Model: each day starts at `bankroll` (prior day settled overnight). Fires processed in t_star order; before
each, capital from earlier SELL99 exits whose sell-time has passed is returned (with pnl) and made available.
Concurrent exposure capped at 60% of day-start bankroll (the runner's daily cap = a CONCURRENT limit here).
HOLD returns capital+pnl only at day end. Compounded over the sample days; report median daily return.
"""
import json, os, math, random, statistics as st, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_trackA_results_raw.json")
SPREAD, DEPTH_CAP, PER_FIRE_CAP, CONC_CAP = 0.02, 25, 0.05, 0.60
MINS = [0, 1, 2, 5, 10, 30, 60]


def fee(p):
    p = min(0.99, max(0.01, p)); return math.ceil(0.07 * p * (1 - p) * 100) / 100.0


def load():
    raw = json.load(open(RAW)); out = []
    for rec in raw:
        c = rec["cells"].get("1_3")
        if not c or not c.get("fired") or c["exec_price"] >= 0.99:
            continue
        ts = c.get("t_star")
        try:
            t = dt.datetime.fromisoformat(ts); minute = t.hour * 60 + t.minute
        except Exception:
            minute = 12 * 60
        decay = {int(k): v for k, v in c.get("decay_gap_by_min", {}).items()}
        # first minute (relative) the ask reaches >=99c
        conv = None
        for m in MINS:
            g = decay.get(m)
            if g is not None and (1 - g) >= 0.99:
                conv = m; break
        out.append({"date": rec["date"], "city": rec.get("city", "?"), "price": c["exec_price"],
                    "outcome": c.get("outcome", 1 if c["pnl"] > 0 else 0), "t": minute, "conv": conv})
    return out


def kelly(price, p=0.9965):
    q = 1 - p; b = (1 - price) / price; return max(0.0, p - q / b)


def sim_day(fires, bank0, mode):
    """One day. mode='hold' or 'sell99'. Returns end-of-day pnl (realized)."""
    fires = sorted(fires, key=lambda f: f["t"])
    avail = bank0
    conc = 0.0                      # concurrent deployed
    pending = []                    # (return_minute, capital, pnl) for sell99 exits
    city_spent = defaultdict(float)
    realized = 0.0
    for f in fires:
        # return matured sell99 positions first
        if mode == "sell99":
            still = []
            for rmin, cap, pnl in pending:
                if rmin <= f["t"]:
                    avail += cap + pnl; conc -= cap; realized += pnl
                else:
                    still.append((rmin, cap, pnl))
            pending = still
        price = f["price"]
        frac = min(0.25 * kelly(price), PER_FIRE_CAP)
        budget = min(frac * bank0, 0.175 * bank0 - city_spent[f["city"]],
                     avail, CONC_CAP * bank0 - conc)
        if budget <= 0:
            continue
        n = min(int(budget / price), DEPTH_CAP)
        if n < 1:
            continue
        cost = n * price
        city_spent[f["city"]] += cost
        avail -= cost; conc += cost
        if mode == "hold":
            realized += n * (f["outcome"] - price - fee(price))   # settles at day end (capital stays locked)
        else:  # sell99
            if f["conv"] is not None:
                sellp = max(0.01, 0.99 - SPREAD)                  # sold at ~99c ask -> hit the bid ~97c
                pnl = n * (sellp - price - fee(price) - fee(sellp))
                pending.append((f["t"] + f["conv"] + 1, cost, pnl))   # capital back shortly after convergence
            else:
                realized += n * (f["outcome"] - price - fee(price))   # never converged -> held to settle
    # settle any still-pending at their pnl (end of day)
    for _, cap, pnl in pending:
        realized += pnl
    return realized


def run(fires_by_day, day_keys, bank0, mode, days=60, trials=3000, seed=7):
    rng = random.Random(seed); daily = []
    for _ in range(trials):
        bank = bank0
        for _d in range(days):
            d = rng.choice(day_keys)
            pnl = sim_day(fires_by_day[d], bank, mode)
            if bank > 0:
                daily.append(pnl / bank)
            bank += pnl
            if bank <= 0:
                break
    daily.sort()
    return st.median(daily) * 100, st.mean(daily) * 100


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=60); ap.add_argument("--trials", type=int, default=3000)
    args = ap.parse_args()
    fires = load()
    by = defaultdict(list)
    for f in fires:
        by[f["date"]].append(f)
    dk = list(by)
    conv = sum(1 for f in fires if f["conv"] is not None)
    print(f"turnover sim | {len(fires)} fires ({100*conv/len(fires):.0f}% converge to 99c) / {len(dk)} days | "
          f"{args.days}d x {args.trials} trials\n")
    print(f"{'bankroll':>10}{'HOLD med/day':>16}{'SELL99 med/day':>16}{'HOLD mean':>12}{'SELL99 mean':>13}")
    for bank in (50, 100, 200, 500, 2000):
        hm, ha = run(by, dk, bank, "hold", args.days, args.trials)
        sm, sa = run(by, dk, bank, "sell99", args.days, args.trials)
        print(f"${bank:>9.0f}{hm:>15.2f}%{sm:>15.2f}%{ha:>11.2f}%{sa:>12.2f}%")
    print("\nSELL99 recycles capital (frees ~89% of winners ~14min after entry). If SELL99 med/day > HOLD at "
          "small bankroll, turnover wins there; if equal/less at large bankroll, capital wasn't the constraint.")


if __name__ == "__main__":
    main()
