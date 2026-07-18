#!/usr/bin/env python3
"""kwx_exit_rules.py -- test EXIT/TAKE-PROFIT rules vs hold-to-settlement (capital turnover + tail dodge).

Motivating data fact: LOSING deployable fires (CLI disagrees) NEVER converge to ~99c intraday (0/6) -- their
price stays wide to settlement, where the -1.0 detonates. 88% of WINNERS reach >=99c intraday. So the market
itself flags losers by refusing to reprice them. Two consequences to test:
  (b) SELL-EARLY / TIME-STOP -> we're OUT before the settlement crash on losers -> lower tail.
  (a) SELL-AT-99 -> frees capital hours before evening settlement -> more turnover on a small bankroll.

We compare, on the real deployable fires (config 1_3), aggregate EV/ct, win%, worst loss, and mean capital-
hold-time, for:
  HOLD        : hold to settlement (current). pnl = outcome - price - fee.
  SELL99      : if ask reaches >=99c at minute k, sell into the bid (~ask-2c spread); else hold to settle.
  TIMESTOP(T) : sell at 99c if reached before T; else sell at the market (bid) at minute T regardless.
Sell price is conservative: bid = (1 - gap) - SPREAD, and a second fee is paid on the sell.

Usage: python kwx_exit_rules.py
"""
import json, os, math, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_trackA_results_raw.json")
SPREAD = 0.02          # conservative: we sell into the bid, ~2c below the ask
MINS = [0, 1, 2, 5, 10, 30, 60]


def fee(p):
    p = min(0.99, max(0.01, p))
    return math.ceil(0.07 * p * (1 - p) * 100) / 100.0


def load():
    raw = json.load(open(RAW))
    out = []
    for rec in raw:
        c = rec["cells"].get("1_3")
        if not c or not c.get("fired") or c["exec_price"] >= 0.99:
            continue
        out.append({"price": c["exec_price"], "outcome": c.get("outcome", 1 if c["pnl"] > 0 else 0),
                    "decay": {int(k): v for k, v in c.get("decay_gap_by_min", {}).items()}})
    return out


def ask_at(f, m):
    g = f["decay"].get(m)
    return None if g is None else max(0.01, min(0.999, 1 - g))


def first_reach_99(f):
    for m in MINS:
        a = ask_at(f, m)
        if a is not None and a >= 0.99:
            return m
    return None


def pnl_hold(f):
    return f["outcome"] - f["price"] - fee(f["price"])


def pnl_sell99(f):
    m = first_reach_99(f)
    if m is None:
        return pnl_hold(f), None                       # never converged -> hold to settle
    sell = max(0.01, ask_at(f, m) - SPREAD)            # hit the bid
    return sell - f["price"] - fee(f["price"]) - fee(sell), m


def pnl_timestop(f, T):
    m = first_reach_99(f)
    if m is not None and m <= T:                       # took profit at 99 before the stop
        sell = max(0.01, ask_at(f, m) - SPREAD)
        return sell - f["price"] - fee(f["price"]) - fee(sell), m
    aT = ask_at(f, T)
    if aT is None:
        return pnl_hold(f), None
    sell = max(0.01, aT - SPREAD)                       # exit at market at T regardless
    return sell - f["price"] - fee(f["price"]) - fee(sell), T


def summarize(name, pnls_holdtimes):
    pnls = [p for p, _ in pnls_holdtimes]
    holds = [h for _, h in pnls_holdtimes if h is not None]
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    losses = [p for p in pnls if p < 0]
    ev = st.mean(pnls)
    worst = min(pnls)
    mean_hold = st.mean(holds) if holds else float("nan")
    # % of capital-hold that is intraday (freed before settlement) = fraction with a finite hold time
    freed_early = sum(1 for _, h in pnls_holdtimes if h is not None) / n
    print(f"{name:>16}{n:>6}{ev:>+9.4f}{100*wins/n:>8.1f}%{len(losses):>7}{worst:>+9.3f}"
          f"{mean_hold:>9.1f}{100*freed_early:>10.0f}%")


def main():
    fires = load()
    print(f"exit-rule test on {len(fires)} deployable fires (1_3), sell spread {SPREAD*100:.0f}c, 2nd fee on sells\n")
    print(f"{'rule':>16}{'n':>6}{'EV/ct':>9}{'win%':>9}{'nLoss':>7}{'worst':>9}{'mHold(min)':>9}{'freedEarly':>11}")
    summarize("HOLD(settle)", [(pnl_hold(f), None) for f in fires])
    summarize("SELL99", [pnl_sell99(f) for f in fires])
    for T in (5, 10, 30, 60):
        summarize(f"TIMESTOP {T}m", [pnl_timestop(f, T) for f in fires])
    print("\nEV/ct net of a 2c sell-spread + double fee. 'worst' = worst single-fire pnl (the tail). "
          "'freedEarly' = % of positions closed BEFORE evening settlement (-> capital recyclable).")
    # tail focus: how do the settlement losers fare under each rule?
    print("\n=== the 6 settlement-losers under each rule (does exiting dodge the -1.0?) ===")
    losers = [f for f in fires if f["outcome"] == 0]
    print(f"{'entry':>7}{'HOLD':>9}{'SELL99':>9}{'STOP30':>9}{'STOP60':>9}")
    for f in losers:
        print(f"{f['price']:>7.2f}{pnl_hold(f):>+9.3f}{pnl_sell99(f)[0]:>+9.3f}"
              f"{pnl_timestop(f,30)[0]:>+9.3f}{pnl_timestop(f,60)[0]:>+9.3f}")


if __name__ == "__main__":
    main()
