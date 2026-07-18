#!/usr/bin/env python3
"""kwx_metrics.py -- RICH performance metrics for the K-WX weather-nowcast edge (operator: "to evaluate
these we need more performance metrics").

The exit-rule / conviction studies reported EV/ct + worst-loss + freedEarly. Those answer "is the mechanism
positive?" but not "how good is it as a bankroll strategy?" This module adds the two metric families that
actually drive a sizing/deploy decision:

  A) CONTRACT-LEVEL (per settled contract, no compounding) -- how clean is the raw edge?
       n, win%, EV/ct, stdev, Sharpe/ct (EV/stdev), Sortino/ct (EV/downside-dev), worst, best,
       profit-factor (gross win $ / gross loss $), and a day-clustered t-stat (real significance,
       clustering by day so one hot day can't masquerade as many independent wins).
     Reported for the three exit rules (HOLD / SELL99 / TIMESTOP30) so the operator can compare them on
     more than EV -- e.g. SELL99 trades EV for a *better worst-loss and higher win%*, which only a
     tail-aware metric (Sortino, worst, profit-factor) reveals.

  B) DAILY-RETURN (Monte-Carlo over real fire days, WITH the honest stressors + caps from the sizing sim) --
     how does it behave as a compounding bankroll? median/day, mean/day, stdev/day, daily Sharpe & Sortino,
     % profitable days, median max-drawdown, p5/p95 day, worst day, ruin%. Reported for FLAT-5% vs the
     CONVICTION tier (cushion>=2F & gap>=15c -> 12% cap) so the operator sees what conviction does to the
     WHOLE distribution (not just median growth): tail, drawdown, and day-to-day volatility.

Everything reuses the same real fires (config 1_3, deployable) and the same fee/stressor assumptions as the
committed studies, so these numbers are directly comparable to kwx_exit_rules.py / kwx_conviction_sizing.py.

Usage:
  python kwx_metrics.py                      # both tables, default bankroll $150 (the cap-binding regime)
  python kwx_metrics.py --bankroll 50 --trials 4000
"""
import argparse, math, random, statistics as st
from collections import defaultdict

import kwx_exit_rules as X            # HOLD/SELL99/TIMESTOP pnl per fire (contract-level)
import kwx_conviction_sizing as C     # fire loader + fee + conviction flags (daily-return sim)


# ----------------------------- A) contract-level metrics -----------------------------
def _daycluster_t(pnls_by_day):
    """Day-clustered t-stat of mean pnl/ct: treat each day's mean as one observation (kills pseudo-replication
    from many correlated same-day fires). t = mean(daymeans) / SE(daymeans)."""
    dm = [st.mean(v) for v in pnls_by_day.values() if v]
    if len(dm) < 2 or st.stdev(dm) == 0:
        return float("nan")
    return st.mean(dm) / (st.stdev(dm) / math.sqrt(len(dm)))


def contract_metrics(name, pnls, days):
    """pnls: list of per-fire pnl/ct. days: parallel list of the fire's date (for clustering). Returns a dict
    of contract-level performance metrics."""
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    ev = st.mean(pnls)
    sd = st.stdev(pnls) if n > 1 else 0.0
    downside = [min(0.0, p) for p in pnls]
    dd = math.sqrt(st.mean([d * d for d in downside])) if n else 0.0        # downside deviation vs 0
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    byday = defaultdict(list)
    for p, d in zip(pnls, days):
        byday[d].append(p)
    return {
        "name": name, "n": n,
        "win": len(wins) / n if n else float("nan"),
        "ev": ev, "sd": sd,
        "sharpe": ev / sd if sd > 0 else float("nan"),        # per-contract Sharpe (edge per unit risk)
        "sortino": ev / dd if dd > 0 else float("inf"),       # per-contract Sortino (edge per unit downside)
        "worst": min(pnls), "best": max(pnls),
        "pf": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),  # profit factor
        "t": _daycluster_t(byday),
    }


def contract_table(latency):
    """Compute contract-level metrics for HOLD / SELL99 / TIMESTOP30 on the real deployable fires."""
    fires = X.load()
    # kwx_exit_rules.load() doesn't carry the date; re-derive it from the conviction loader (same fire set,
    # same 1_3 filter) so we can day-cluster. Align by index isn't safe -> rebuild pnls from X on C's fires.
    cf = C.load_fires(latency)
    days = [f["date"] for f in cf]
    # X.load() and C.load_fires() both iterate the raw in the same order with the same 1_3/exec<0.99 filter,
    # but C also drops price>=0.99 at `latency`; to stay 1:1 we recompute exit pnls on X.load()'s fires and
    # pull dates from a parallel X-order date list.
    xfires = X.load()
    xdays = _dates_for_xfires()
    hold = [X.pnl_hold(f) for f in xfires]
    sell = [X.pnl_sell99(f)[0] for f in xfires]
    stop = [X.pnl_timestop(f, 30)[0] for f in xfires]
    rows = [contract_metrics("HOLD(settle)", hold, xdays),
            contract_metrics("SELL99", sell, xdays),
            contract_metrics("TIMESTOP30", stop, xdays)]
    return rows


def _dates_for_xfires():
    """Dates parallel to kwx_exit_rules.load()'s fire order (same raw iteration + same 1_3 filter)."""
    import json, os
    raw = json.load(open(X.RAW))
    out = []
    for rec in raw:
        c = rec["cells"].get("1_3")
        if not c or not c.get("fired") or c["exec_price"] >= 0.99:
            continue
        out.append(rec["date"])
    return out


# ----------------------------- B) daily-return metrics -----------------------------
def daily_returns(by_day, day_keys, base_cap, conv_cap, bankroll0, days, trials,
                  unfill=0.21, baddays=0.02, conv_tail=0.005, seed=101):
    """Monte-Carlo the compounding bankroll (same engine/stressors as kwx_conviction_sizing.simulate) but
    RECORD every per-day return so we can compute Sharpe/Sortino/%prof/drawdown, not just the final multiple.
    Returns (daily_return_list, per_trial_maxdd_list, ruin_frac)."""
    rng = random.Random(seed)
    daily, mdds, ruined = [], [], 0
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
            DAILY_CAP = 0.60 * bank
            dpnl = 0.0
            for f in sorted(fires, key=lambda x: x["price"]):
                if rng.random() < unfill:
                    continue
                price = f["price"]
                conv = f["conviction"]
                p = C.WINP_CONV if conv else C.WINP_BASE
                cap = conv_cap if conv else base_cap
                frac = min(0.25 * C.kelly_frac(price, p), cap)
                budget = min(frac * bank, 0.175 * bank - city_spent[f["city"]], avail, DAILY_CAP - day_deployed)
                if budget <= 0:
                    continue
                n = min(int(budget / price), C.DEPTH_CAP)
                if n < 1:
                    continue
                city_spent[f["city"]] += n * price
                avail -= n * price
                day_deployed += n * price
                if bad:
                    pnl_ct = -price - C.kalshi_fee(price)
                elif conv and rng.random() < conv_tail:
                    pnl_ct = -price - C.kalshi_fee(price)
                else:
                    pnl_ct = f["pnl"]
                dpnl += n * pnl_ct
            start = bank
            if start > 0:
                daily.append(dpnl / start)
            bank += dpnl
            peak = max(peak, bank)
            mdd = max(mdd, (peak - bank) / peak if peak > 0 else 0.0)
            if bank <= RUIN:
                ruin_hit = True
        mdds.append(mdd)
        ruined += ruin_hit
    return daily, mdds, ruined / trials


def daily_metrics(name, daily, mdds, ruin):
    d = sorted(daily)
    n = len(d)
    mean = st.mean(d)
    sd = st.stdev(d) if n > 1 else 0.0
    downside = [min(0.0, x) for x in d]
    dd = math.sqrt(st.mean([x * x for x in downside])) if n else 0.0
    prof = sum(1 for x in d if x > 0) / n if n else float("nan")
    return {
        "name": name,
        "median": st.median(d), "mean": mean, "sd": sd,
        "sharpe": mean / sd if sd > 0 else float("nan"),      # daily Sharpe (not annualized)
        "sortino": mean / dd if dd > 0 else float("inf"),     # daily Sortino
        "prof": prof,
        "p5": d[max(0, n // 20)], "p95": d[min(n - 1, n - n // 20)],
        "worst": d[0],
        "mdd": st.median(mdds) if mdds else float("nan"),
        "ruin": ruin,
    }


def daily_table(latency, bankroll, days, trials):
    fires = C.load_fires(latency)
    by_day = defaultdict(list)
    for f in fires:
        by_day[f["date"]].append(f)
    dk = list(by_day)
    nconv = sum(1 for f in fires if f["conviction"])
    # FLAT 5% (conviction cap == base cap == 5%) vs CONVICTION tier (12% cap on cushion>=2F & gap>=15c)
    fd, fm, fr = daily_returns(by_day, dk, 0.05, 0.05, bankroll, days, trials)
    cd, cm, cr = daily_returns(by_day, dk, 0.05, 0.12, bankroll, days, trials)
    return nconv, len(fires), len(dk), [daily_metrics("FLAT 5%", fd, fm, fr),
                                        daily_metrics("CONVICTION 12%", cd, cm, cr)]


# ----------------------------- report -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bankroll", type=float, default=150.0)   # small = the cap-binding regime (where sizing matters)
    ap.add_argument("--latency", type=int, default=5)
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--trials", type=int, default=4000)
    args = ap.parse_args()

    print("=" * 96)
    print("K-WX PERFORMANCE METRICS  (real deployable fires, config 1_3; same fees/stressors as the studies)")
    print("=" * 96)

    # A) contract-level
    rows = contract_table(args.latency)
    print(f"\nA) CONTRACT-LEVEL (per settled contract, no compounding) -- exit rule comparison\n")
    print(f"{'rule':>14}{'n':>6}{'win%':>7}{'EV/ct':>8}{'stdev':>8}{'Sharpe':>8}{'Sortino':>9}"
          f"{'worst':>8}{'best':>7}{'PF':>7}{'t(day)':>8}")
    for m in rows:
        sortino = "inf" if m["sortino"] == float("inf") else f"{m['sortino']:.2f}"
        pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
        print(f"{m['name']:>14}{m['n']:>6}{100*m['win']:>6.1f}%{m['ev']:>+8.3f}{m['sd']:>8.3f}"
              f"{m['sharpe']:>8.3f}{sortino:>9}{m['worst']:>+8.3f}{m['best']:>+7.3f}{pf:>7}{m['t']:>8.2f}")
    print("\n  Sharpe/ct = EV per unit of fire-to-fire stdev; Sortino/ct = EV per unit of DOWNSIDE deviation "
          "(tail-aware).\n  PF = gross win$ / gross loss$ (>1 profitable; higher = more loss-tolerant). "
          "t(day) = day-clustered significance.")

    # B) daily-return
    nconv, nf, nd, drows = daily_table(args.latency, args.bankroll, args.days, args.trials)
    print(f"\nB) DAILY-RETURN (MC, ${args.bankroll:.0f} bankroll, {args.latency}min latency, {nf} fires / {nd} days, "
          f"{nconv} conviction; {args.days}d x {args.trials} trials)")
    print("   stressors ON: 21% unfillable, 2%/day heat-dome, 0.5% conviction model-error tail, 60%/day + depth caps\n")
    print(f"{'sizing':>16}{'med/day':>9}{'mean/day':>10}{'stdev':>8}{'Sharpe_d':>10}{'Sortino_d':>11}"
          f"{'profDay%':>10}{'p5day':>8}{'worstday':>10}{'maxDD':>8}{'ruin%':>7}")
    for m in drows:
        sortino = "inf" if m["sortino"] == float("inf") else f"{m['sortino']:.2f}"
        print(f"{m['name']:>16}{100*m['median']:>8.2f}%{100*m['mean']:>9.2f}%{100*m['sd']:>7.1f}%"
              f"{m['sharpe']:>10.3f}{sortino:>11}{100*m['prof']:>9.1f}%{100*m['p5']:>7.1f}%"
              f"{100*m['worst']:>9.1f}%{100*m['mdd']:>7.1f}%{100*m['ruin']:>6.2f}")
    print("\n  Sharpe_d/Sortino_d = per-DAY (not annualized). profDay% = share of days with positive return. "
          "maxDD = median peak-to-trough over the run.\n  Read: conviction should lift median/mean/Sharpe "
          "WITHOUT wrecking worstday/maxDD/ruin -- if the tail columns hold, the upsize is 'free'.")


if __name__ == "__main__":
    main()
