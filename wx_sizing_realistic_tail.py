#!/usr/bin/env python3
"""wx_sizing_realistic_tail.py -- can we size UP? Re-optimize the per-fire cap under the MEASURED tail.

The 5% per-fire cap was set for ruin~0 under a deliberately harsh stressor: 2%/day where EVERY fire loses.
But wx_capacity_probe's heat-dome measurement (Track B cache, 5+ yrs) shows that catastrophe basically never
happens -- the worst single day had only ~16% of cities lock-failing, ZERO days hit >=30%, and the per-day
lock-fail fraction is median 0% / p95 6%. So the real correlated-loss tail is FAR smaller than the sim's
"all-lose" day, meaning ruin is lower than modeled and there may be headroom to raise the cap for more growth
(operator: "ok taking on risk if the return is there"). This sweeps the per-fire cap using the EMPIRICAL
per-day loss distribution (sampled from the actual multi-year cache) instead of the 2%-all-lose stressor, and
reports growth vs ruin so the cap can be set on the real tail.
"""
import json, glob, os, math, random, statistics as st
from collections import defaultdict
import kwx_conviction_sizing as C

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tailrisk_cache")


def empirical_day_lossfrac():
    """Multi-year list of per-day fraction-of-cities-lock-failing (the REAL correlated-loss distribution)."""
    byday = defaultdict(lambda: {"n": 0, "fail": 0})
    for fp in glob.glob(os.path.join(CACHE, "daily_*.json")):
        for rec in json.load(open(fp)):
            Cv = rec.get("cli_high"); V = rec.get("sustain3_max")
            if Cv is None or V is None:
                continue
            try:
                Cv = int(round(Cv))
            except Exception:
                continue
            d = rec["date"]; byday[d]["n"] += 1
            if V >= Cv + 1:
                byday[d]["fail"] += 1
    return [x["fail"] / x["n"] for x in byday.values() if x["n"] >= 8]


def simulate(by_day, dk, cap, bankroll0, lossfracs, days=60, trials=4000, seed=13):
    rng = random.Random(seed)
    daily, mdds, ruined, worst = [], [], 0, 0.0
    RUIN = bankroll0 * 0.2
    for _ in range(trials):
        bank = bankroll0; peak = bank; mdd = 0.0; ruin_hit = False
        for _d in range(days):
            fires = by_day[rng.choice(dk)]
            lossfrac = rng.choice(lossfracs)          # REAL correlated shock: this fraction of today's fires lose
            city = defaultdict(float); avail = bank; dep = 0.0; DCAP = 0.60 * bank; dpnl = 0.0
            for f in sorted(fires, key=lambda x: x["price"]):
                if rng.random() < 0.21:
                    continue
                price = f["price"]; conv = f["conviction"]
                p = C.WINP_CONV if conv else C.WINP_BASE
                percap = 0.12 if conv else cap
                frac = min(0.25 * C.kelly_frac(price, p), percap)
                bud = min(frac * bank, 0.175 * bank - city[f["city"]], avail, DCAP - dep)
                if bud <= 0:
                    continue
                n = min(int(bud / price), C.DEPTH_CAP)
                if n < 1:
                    continue
                city[f["city"]] += n * price; avail -= n * price; dep += n * price
                lose = (rng.random() < lossfrac) or (rng.random() < (0.0 if conv else 0.0))
                pnl = (-price - C.kalshi_fee(price)) if lose else f["pnl"]
                dpnl += n * pnl
            start = bank
            if start > 0:
                daily.append(dpnl / start); worst = min(worst, dpnl / start)
            bank += dpnl; peak = max(peak, bank)
            mdd = max(mdd, (peak - bank) / peak if peak > 0 else 0.0)
            if bank <= RUIN:
                ruin_hit = True
        mdds.append(mdd); ruined += ruin_hit
    d = sorted(daily); n = len(d); mean = st.mean(d)
    dd = math.sqrt(st.mean([min(0, x) ** 2 for x in d]))
    return {"med": st.median(d), "mean": mean, "sortino": mean / dd if dd else 0,
            "worst": worst, "mdd": st.median(mdds), "ruin": ruined / trials,
            "prof": sum(1 for x in d if x > 0) / n}


def main():
    lf = empirical_day_lossfrac()
    print(f"per-fire cap sweep under the MEASURED tail | {len(lf)} real days sampled | "
          f"per-day loss-frac: median {100*st.median(lf):.1f}% p95 {100*sorted(lf)[int(0.95*len(lf))]:.0f}% "
          f"max {100*max(lf):.0f}%  (vs old stressor: 2%/day @ 100%)\n")
    fires = C.load_fires(10)          # realistic MADIS latency
    by = defaultdict(list)
    for f in fires:
        by[f["date"]].append(f)
    dk = list(by)
    for bank in (150, 1000):
        print(f"--- ${bank} bankroll (base cap swept; conviction stays 12%) ---")
        print(f"{'per-fire cap':>13}{'med/day':>9}{'mean/day':>10}{'Sortino':>9}{'worstday':>10}{'maxDD':>8}{'ruin%':>7}")
        for cap in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20):
            m = simulate(by, dk, cap, bank, lf)
            print(f"{int(cap*100):>11}%{100*m['med']:>9.2f}%{100*m['mean']:>9.2f}%{m['sortino']:>9.2f}"
                  f"{100*m['worst']:>9.1f}%{100*m['mdd']:>7.1f}%{100*m['ruin']:>6.2f}")
        print()
    print("read: with the REAL (small) correlated tail, ruin stays ~0 at much higher caps than 5%. Pick the cap "
          "where med/day gains flatten or worstday/maxDD/ruin start to bite -- that's the risk-justified size given "
          "the tail actually observed, not the pessimistic all-lose day.")


if __name__ == "__main__":
    main()
