#!/usr/bin/env python3
"""wx_fee_floor_impact.py -- QUANTIFY the fee-aware entry floor on real recorded Track A fires (offline).

The runner's sizing was fee-blind: Kelly/EV used the gross gap (100 - ask) and ignored the Kalshi quadratic
taker fee ceil(0.07*p*(1-p)) per contract, which is worst exactly where the gap is thinnest (a 98c entry has
a 2c gross gap but a 1c fee -- half the apparent edge never existed). Before changing any live entry rule,
the statistical-soundness bar is: show, on recorded data, what the rule would have excluded and what those
exclusions actually earned. This script does that against _trackA_results_raw.json (the Phase-2 Track A
walk-forward raw grid: one record per market-day, `cells` keyed margin_sustain, each fired cell carrying
exec_price [0-1 dollars], fee [unrounded quadratic], pnl [net of that fee], gap).

Floor under test: skip any fire whose gross gap (100 - ask_c) <= fee_c + MIN_NET_EDGE_C, with the live
ceil'd fee. Two baselines matter and are both reported:
  * RAW (all fired cells): includes 99c/100c fires the live runner ALREADY excludes via MAX_PAY_CENTS=98,
    so the floor looks dramatic here -- but that credit belongs to the existing cap, not the floor.
  * LIVE-ADMISSIBLE (ask <= 98c): the honest baseline. The floor's MARGINAL effect at margin=1c is exactly
    the 98c fires; that set decides whether the 1c margin is evidence-backed.

VERDICT (why the shipped default is MIN_NET_EDGE_C=0, i.e. arithmetic-only, a no-op vs MAX_PAY_CENTS):
the 98c fires the 1c margin would exclude were EV-POSITIVE in sample (all wins), so the soundness rule --
no param change without supporting evidence -- forbids excluding them. At 0 the floor only rejects entries
whose winning payoff (gap - fee) is <= 0, which cannot profit even on a win: pure arithmetic, no evidence
needed. Run this again as live data accrues; a single recorded 98c loss (-99c net) would flip the math.

PROPOSE-ONLY: reads the recorded backtest file, prints numbers. Never trades, never touches live params.

Usage: python wx_fee_floor_impact.py    # prints the impact table for the deployed cell (margin=1/sustain=3)
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# Pull the fee/floor constants and formula straight from the production runner instead of keeping private
# copies here -- that way this analysis validates the ACTUAL deployed rule, not a maybe-stale mirror of it.
from kwx_runner import _kalshi_fee_c as fee_c, MIN_NET_EDGE_C, MAX_PAY_CENTS, MARGIN_F, SUSTAIN_MIN

RAW = os.path.join(HERE, "_trackA_results_raw.json")
DEPLOYED_CELL = f"{int(MARGIN_F)}_{SUSTAIN_MIN}"  # frozen live config (kwx_runner.MARGIN_F/SUSTAIN_MIN)
P_BREAKEVEN_98 = 0.99     # at 98c net of the 1c ceil'd fee: win +1c / lose -99c -> breakeven win rate 99.0%


def excluded_by_floor(price_c, margin_c):
    return (100 - price_c) <= fee_c(price_c) + margin_c


def ev_ct(fires):
    return sum(f["pnl"] for f in fires) / len(fires) if fires else 0.0


def report(fires, label, margin_c):
    keep = [f for f in fires if not excluded_by_floor(round(f["exec_price"] * 100), margin_c)]
    excl = [f for f in fires if excluded_by_floor(round(f["exec_price"] * 100), margin_c)]
    wins = sum(1 for f in excl if f["outcome"] == 1.0)
    print(f"\n{label} (n={len(fires)}), floor margin = {margin_c}c:")
    print(f"  excluded fires : {len(excl)}  (wins {wins}/{len(excl)})")
    print(f"  excluded pnl   : {sum(f['pnl'] for f in excl):+.4f} $ aggregate, {ev_ct(excl):+.5f} $/ct")
    print(f"  EV/ct before   : {ev_ct(fires):+.4f} $/ct")
    print(f"  EV/ct after    : {ev_ct(keep):+.4f} $/ct  (on {len(keep)} kept fires)")
    return excl


def main():
    data = json.load(open(RAW))
    fires = [r["cells"][DEPLOYED_CELL] for r in data
             if r["cells"].get(DEPLOYED_CELL, {}).get("fired")]
    print(f"deployed cell {DEPLOYED_CELL}: {len(fires)} recorded fires across {len(data)} market-days")
    print(f"kwx_runner.MIN_NET_EDGE_C (live, currently deployed) = {MIN_NET_EDGE_C}")

    # RAW baseline -- inflated by 99c/100c fires MAX_PAY_CENTS already excludes; shown for completeness only.
    report(fires, "RAW (all fired cells; 99c/100c already dead under MAX_PAY_CENTS)", 1)

    # LIVE-ADMISSIBLE baseline -- the decision-relevant view: what would the floor NEWLY exclude?
    adm = [f for f in fires if round(f["exec_price"] * 100) <= MAX_PAY_CENTS]
    excl = report(adm, f"LIVE-ADMISSIBLE (ask <= {MAX_PAY_CENTS}c -- the honest baseline)", 1)

    # The marginal set is the 98c fires: what did they earn under the LIVE ceil'd fee (win nets exactly 1c)?
    n, wins = len(excl), sum(1 for f in excl if f["outcome"] == 1.0)
    live_pnl = wins * 0.01 - (n - wins) * 0.99   # ceil'd-fee economics: +1c per win, -99c per loss
    print(f"\n98c marginal set under the LIVE ceil'd fee (+1c win / -99c loss):")
    print(f"  {wins}/{n} wins -> {live_pnl:+.2f} $ aggregate, {live_pnl / n if n else 0:+.5f} $/ct")
    print(f"  breakeven win rate at 98c: {P_BREAKEVEN_98:.1%}; observed {wins / n if n else 0:.1%}")
    # Rule of three: 0 losses in n trials -> 95% upper bound on the loss rate ~ 3/n. Honesty requires noting
    # the CI straddles breakeven -- but "can't rule out negative" is not evidence FOR exclusion.
    if n and wins == n:
        print(f"  rule-of-three 95% upper bound on loss rate: {3 / n:.2%} (breakeven loss rate: "
              f"{1 - P_BREAKEVEN_98:.2%}) -> positive net EV NOT statistically confirmed, but observed "
              f"pnl is positive: no evidence to exclude")

    recommended = 1 if ev_ct(excl) < 0 else 0
    match = "MATCHES" if MIN_NET_EDGE_C == recommended else "MISMATCH vs"
    print(f"\nVERDICT: the 1c-margin floor's exclusions were EV-{'NEGATIVE' if ev_ct(excl) < 0 else 'POSITIVE'} "
          f"in sample -> data-recommended MIN_NET_EDGE_C = {recommended} "
          f"({'floor active at fee+1c' if recommended else 'arithmetic-only floor; no-op vs MAX_PAY_CENTS'})"
          f" -- {match} the deployed kwx_runner.MIN_NET_EDGE_C = {MIN_NET_EDGE_C}")


if __name__ == "__main__":
    main()
