#!/usr/bin/env python3
"""kwx_conviction_sizing.py -- data-backed test of CONVICTION-scaled sizing ("press the good ones harder").

Question (operator): when a fire is high-conviction (big cushion AND still cheap), should we size up toward
"unload the clip"? This answers it from the REAL fires, with the honest stressor being the point: the
in-sample loss rate on conviction fires is 0% (350 fires), but 0% from 350 samples has a Wilson-95 upper
bound near ~1% -- so we MUST test what happens when the true tail isn't actually zero, plus a correlated
heat-dome day, because that's exactly the risk upsizing amplifies.

Conviction is defined from the data:
  - CUSHION (safety) = highest strategy-margin m in {1,2,3} whose m_3 cell still fired = how far obs cleared
    the strike. Loss rate empirically: 1-2F 0.93%, 2-3F 0.00%, >=3F 0.00%.
  - GAP (edge) = 1 - exec_price.
  - CONVICTION fire = cushion >= 2F AND gap >= 15c (n=350, 0% in-sample loss, +0.29..0.33/ct).

Sizing rules compared (per-fire fraction-of-bankroll cap; quarter-Kelly within it; per-city day cap 17.5%):
  - FLAT: 5% cap on every fire (the current rule).
  - CONVICTION: base fires 5% cap; CONVICTION fires get a raised cap CONV_CAP (swept 5..100%).
"unload the clip" = CONV_CAP ~ 100%. We find the CONV_CAP where extra growth stops being worth extra ruin.

Honest stressors (all ON): 21% unfillable; 2%/day heat-dome (every fire that day loses); and a MODEL-ERROR
tail on conviction fires -- with prob CONV_TAIL each 'safe' conviction win is flipped to a full loss, to test
robustness to the true conviction loss rate being > the in-sample 0% (swept 0 / 0.5% / 1%).

Usage: python kwx_conviction_sizing.py --bankroll 2000 --latency 5 --days 60 --trials 4000
"""
import json, os, math, argparse, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_trackA_results_raw.json")
DEPTH_CAP = 25          # book can't absorb more than ~this per fire (Tier-1) -- also bounds "unload the clip"
WINP_BASE, WINP_CONV = 0.99, 0.999


def kalshi_fee(p):
    return math.ceil(0.07 * p * (1 - p) * 100) / 100.0


def cushion_of(rec):
    hi = 0
    for m in (1, 2, 3):
        if rec["cells"].get(f"{m}_3", {}).get("fired"):
            hi = m
    return hi


def load_fires(latency_min):
    raw = json.load(open(RAW))
    k = str(latency_min)
    out = []
    for rec in raw:
        c = rec["cells"].get("1_3")
        if not c or not c.get("fired") or c["exec_price"] >= 0.99:
            continue
        gap = c.get("decay_gap_by_min", {}).get(k)
        price = (1.0 - gap) if gap is not None else c["exec_price"]
        price = min(0.99, max(0.01, price))
        if price >= 0.99:
            continue
        outcome = c.get("outcome", 1 if c["pnl"] > 0 else 0)
        cush = cushion_of(rec)
        gap_now = 1.0 - price
        conviction = (cush >= 2 and gap_now >= 0.15)
        out.append({"date": rec["date"], "city": rec.get("city", "?"), "price": price,
                    "outcome": outcome, "pnl": outcome - price - kalshi_fee(price),
                    "cushion": cush, "gap": gap_now, "conviction": conviction})
    return out


def kelly_frac(price, p):
    q = 1 - p
    b = (1 - price) / price
    return max(0.0, p - q / b)


def simulate(by_day, day_keys, base_cap, conv_cap, bankroll0, days, trials,
             unfill=0.21, baddays=0.02, conv_tail=0.005, seed=101):
    rng = random.Random(seed)
    finals, mdds, ruined, netloss, worstday = [], [], 0, 0, 0.0
    RUIN = bankroll0 * 0.2
    for _ in range(trials):
        bank = bankroll0
        peak = bank
        mdd = 0.0
        ruin_hit = False
        for _d in range(days):
            day = rng.choice(day_keys)
            fires = by_day[day]
            bad = rng.random() < baddays
            city_spent = defaultdict(float)
            avail = bank
            day_deployed = 0.0
            DAILY_CAP = 0.60 * bank        # runner's real MAX_DAILY_DEPLOY_FRAC -- bounds the heat-dome day
            dpnl = 0.0
            for f in sorted(fires, key=lambda x: x["price"]):
                if rng.random() < unfill:
                    continue
                price = f["price"]
                conv = f["conviction"]
                p = WINP_CONV if conv else WINP_BASE
                cap = conv_cap if conv else base_cap
                frac = min(0.25 * kelly_frac(price, p), cap)
                budget = min(frac * bank, 0.175 * bank - city_spent[f["city"]], avail,
                             DAILY_CAP - day_deployed)
                if budget <= 0:
                    continue
                n = int(budget / price)
                n = min(n, DEPTH_CAP)
                if n < 1:
                    continue
                city_spent[f["city"]] += n * price
                avail -= n * price
                day_deployed += n * price
                # outcome with stressors
                if bad:
                    pnl_ct = -price - kalshi_fee(price)
                elif conv and rng.random() < conv_tail:   # model-error: 'safe' conviction fire loses anyway
                    pnl_ct = -price - kalshi_fee(price)
                else:
                    pnl_ct = f["pnl"]
                dpnl += n * pnl_ct
            start = bank
            bank += dpnl
            worstday = min(worstday, dpnl / start if start > 0 else 0)
            peak = max(peak, bank)
            mdd = max(mdd, (peak - bank) / peak if peak > 0 else 0)
            if bank <= RUIN:
                ruin_hit = True
        finals.append(bank)
        mdds.append(mdd)
        ruined += ruin_hit
        netloss += bank < bankroll0
    finals.sort()
    n = len(finals)
    return {"median": finals[n // 2], "p5": finals[max(0, n // 20)], "p95": finals[min(n - 1, n - n // 20)],
            "mdd": sorted(mdds)[len(mdds) // 2], "ruin": ruined / trials, "netloss": netloss / trials,
            "worstday": worstday}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bankroll", type=float, default=2000.0)  # size where the per-fire CAP binds (not the $10 floor)
    ap.add_argument("--latency", type=int, default=5, choices=[0, 1, 2, 5, 10, 30, 60])
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--trials", type=int, default=4000)
    args = ap.parse_args()

    fires = load_fires(args.latency)
    by_day = defaultdict(list)
    for f in fires:
        by_day[f["date"]].append(f)
    day_keys = list(by_day)
    nconv = sum(1 for f in fires if f["conviction"])
    print(f"CONVICTION sizing test | ${args.bankroll:.0f} | {args.latency}min latency | {len(fires)} fires "
          f"({nconv} conviction = cushion>=2F & gap>=15c) / {len(day_keys)} days | {args.days}d x {args.trials} trials")
    print("stressors: 21% unfillable, 2%/day heat-dome (all lose), conviction model-error tail swept\n")

    print(f"{'rule':>26}{'convTail':>9}{'medianX':>9}{'p5X':>8}{'ruin%':>7}{'worstDay%':>11}")
    def row(label, base_cap, conv_cap, ct):
        m = simulate(by_day, day_keys, base_cap, conv_cap, args.bankroll, args.days, args.trials, conv_tail=ct)
        print(f"{label:>26}{ct*100:>8.1f}%{m['median']/args.bankroll:>8.1f}x{m['p5']/args.bankroll:>7.1f}x"
              f"{m['ruin']*100:>6.1f}{m['worstday']*100:>10.1f}")
        return m
    # baseline flat 5%
    row("FLAT 5%", 0.05, 0.05, 0.005)
    # conviction cap sweep, at 3 model-error-tail assumptions (0, 0.5%, 1%)
    for ct in (0.0, 0.005, 0.01):
        for cc in (0.10, 0.20, 0.40, 1.00):
            row(f"conviction cap {int(cc*100)}%", 0.05, cc, ct)
    print("\nread: medianX/p5X = multiple of starting bankroll over the run; worstDay% = worst single-day return "
          "seen. 'unload the clip' = conviction cap 100%. The honest test is p5/ruin/worstDay under a NON-zero "
          "conviction tail (0.5-1%), since in-sample 0% is only an estimate.")


if __name__ == "__main__":
    main()
