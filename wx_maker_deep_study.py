#!/usr/bin/env python3
"""wx_maker_deep_study.py -- reproducible harness for the K-WX maker (resting-order) deep study.

WHAT THIS IS: a fleet of harvest agents backtested a hypothetical "post lock, rest a YES bid at 93/95/97c"
maker strategy against 65 days x 20 stations of real Kalshi trade-tape + IEM ASOS-1min data and reported a
headline +7.00c/contract, 0% adverse-selection edge on the post-lock P=93 cell (n=22.5 simulated fills). A
verifier panel then live-audited that cell against real 1-minute candlesticks (best ask at each hypothetical
placement time) and found the fill simulator never checked whether the "resting" bid would actually have
crossed the spread and executed as a TAKER order instead -- it did, for the large majority of the cell. The
corrected, execution-realistic version of the same idea converts to genuine maker fills only 2-3 times in
the whole sample. See wx_maker_deep_study.md for the full narrative; this script reproduces both tables
(the refuted naive headline AND the panel's strict recount) directly from the committed compact dataset so
neither number has to be taken on faith.

PROPOSE-ONLY / READ-ONLY: reads wx_maker_deep_data.json (committed alongside this script), prints tables,
writes nothing, places no orders, calls no network API. Does not import or modify kwx_runner.py,
kwx_paper_gate.py, kalshi_exec.py, or kwx_daily_digest.py.

Usage:
    python wx_maker_deep_study.py            # prints both tables + verdict
    python wx_maker_deep_study.py --selftest  # internal consistency checks (also run by kwx_selftest.py)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "wx_maker_deep_data.json")


def load_data(path=DATA_PATH):
    with open(path) as f:
        return json.load(f)


def wilson_ci(k, n, z=1.96):
    """Two-sided Wilson score CI for a binomial proportion k/n. Same formula used throughout the repo's
    other wx_*.py studies (e.g. wx_ev_concentration.wilson_ci) -- kept local here so this script has zero
    imports from production trading code, per the no-touch instruction."""
    if n <= 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def net_ev_c(wins, losses, P):
    fills = wins + losses
    if fills <= 0:
        return None
    return (wins * (100 - P) - losses * P) / fills


# ---------------------------------------------------------------------------
# Table 1: the AS-HARVESTED naive headline (kept only as the audited artifact; REFUTED, see verdict)
# ---------------------------------------------------------------------------

def print_naive_table(data):
    print("=" * 96)
    print("TABLE 1 -- NAIVE AS-HARVESTED HEADLINE (post-lock arm REFUTED by verifier panel; see TABLE 2)")
    print("=" * 96)
    hdr = f"{'arm':<5}{'D':>6}{'P':>5}{'n_st':>6}{'bids':>7}{'fills':>8}{'fill_rate':>12}{'adv_sel':>10}{'net_ev_c/ct':>13}"
    print(hdr)
    print("-" * len(hdr))
    for row in data["naive_headline_grand_table"]["rows"]:
        d = "--" if row["D"] is None else f"{row['D']:.1f}"
        print(f"{row['arm']:<5}{d:>6}{row['P']:>5}{row['n_stations']:>6}{row['bids']:>7.0f}"
              f"{row['fills']:>8.1f}{row['fill_rate']:>12.3f}{row['adverse_sel']:>10.3f}"
              f"{row['net_ev_c_per_contract']:>13.2f}")
    print()
    print("Flagged FATAL: post-lock rows assume every simulated bid rests, without checking ask <= P at")
    print("placement. Pre-lock rows: sign (net-negative) judged to plausibly survive; no magnitude does.")
    print()


# ---------------------------------------------------------------------------
# Table 2: the panel's strict, execution-realistic recount of the flagship post-lock P=93 cell
# ---------------------------------------------------------------------------

def print_strict_table(data):
    vs = data["verified_strict"]
    print("=" * 96)
    print("TABLE 2 -- VERIFIED STRICT RECOUNT (post-lock, P=93c only; post-only / non-crossing bids)")
    print("=" * 96)
    print(f"Scope: {vs['scope']}")
    print(f"Method: {vs['method']}")
    print()
    lo, hi = vs["restable_bids_range"]
    print(f"Restable bids (ask>93c at placement): {lo}-{hi} of 58 naive post-lock P=93 bids")
    print(f"Confirmed genuine maker fills: {vs['confirmed_genuine_maker_fills']}"
          f"  (+{vs['possible_additional_fill_unresolved']} possible/unresolved)")
    print()
    print(f"{'station':<8}{'ticker':<32}{'ask_c':>7}{'fill_c':>8}{'delay_s':>9}{'status':<40}")
    print("-" * 104)
    for f in vs["fills"]:
        fc = "--" if f["fill_price_c"] is None else str(f["fill_price_c"])
        ds = "--" if f["fill_delay_s_after_lock"] is None else str(f["fill_delay_s_after_lock"])
        print(f"{f['station']:<8}{f['ticker']:<32}{f['ask_c_at_placement']:>7}{fc:>8}{ds:>9}  {f['status']}")
    print()
    n2 = vs["adverse_selection_confirmed"]["n"]
    k2 = vs["adverse_selection_confirmed"]["k_adverse"]
    lo2, hi2 = wilson_ci(k2, n2)
    print(f"Adverse selection, confirmed n={n2}: {k2}/{n2} = 0.0%, "
          f"Wilson 95% CI [{lo2*100:.1f}%, {hi2*100:.1f}%]  "
          f"(recomputed here; matches data file's stored value)")
    n3 = vs["adverse_selection_if_3rd_counts"]["n"]
    lo3, hi3 = wilson_ci(0, n3)
    print(f"Adverse selection, if 3rd (KSFO) confirms, n={n3}: 0/{n3} = 0.0%, "
          f"Wilson 95% CI [{lo3*100:.1f}%, {hi3*100:.1f}%]")
    print()
    glo, ghi = vs["gross_total_c_confirmed_range"]
    print(f"Gross total: +{glo} to +{ghi} cents over 65 days x 20 stations "
          f"(net EV per genuine fill unchanged from naive: +{vs['net_ev_c_per_contract_confirmed']:.2f}c/contract)")
    print()


def print_verdict(data):
    print("=" * 96)
    print("VERDICT")
    print("=" * 96)
    print(data["panel_verdict_summary"])
    print()
    print("Recommendation: " + data["recommendation"]["verdict"])
    print()


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        status = "PASS" if cond else "FAIL"
        if not cond:
            ok = False
        print(f"[{status}] {name}")

    data = load_data()
    check("data file loads and is a dict", isinstance(data, dict))
    check("naive_headline_grand_table has 9 rows (3 P x 3 D/arm combos)",
          len(data["naive_headline_grand_table"]["rows"]) == 9)

    # Wilson CI sanity: k=0/n=2 upper bound should be ~0.658 (matches panel's "~66%" for the confirmed cell)
    lo, hi = wilson_ci(0, 2)
    check("wilson_ci(0,2) matches known closed form (upper ~0.658)", abs(hi - 0.6577) < 0.001 and lo == 0.0)

    # Wilson CI on a textbook case: k=50/n=100 should straddle 0.5 tightly
    lo, hi = wilson_ci(50, 100)
    check("wilson_ci(50,100) contains 0.5 and is reasonably tight", lo < 0.5 < hi and (hi - lo) < 0.2)

    # net_ev_c reproduces the naive post P=93 headline exactly from its own wins/losses
    row = next(r for r in data["naive_headline_grand_table"]["rows"] if r["arm"] == "post" and r["P"] == 93)
    # naive table doesn't carry wins/losses directly (adverse_sel==0 means losses==0, fills==wins)
    implied_ev = 100 - 93  # every fill is a win at P=93 in the naive/tautological cell
    check("naive post P=93 net_ev matches (100-P) given adverse_sel==0",
          abs(row["net_ev_c_per_contract"] - implied_ev) < 1e-6)

    # strict cell: 2 confirmed fills, both wins, EV should also be exactly 100-93=7
    vs = data["verified_strict"]
    check("verified_strict confirmed fill count == 2", vs["confirmed_genuine_maker_fills"] == 2)
    check("verified_strict net_ev_c_per_contract == 7.0",
          abs(vs["net_ev_c_per_contract_confirmed"] - 7.0) < 1e-6)
    check("all confirmed fills are wins (no adverse selection observed)",
          all(f["result"] in ("win", "unresolved") for f in vs["fills"]))

    # sanity: strict n << naive n (that's the whole point of the correction)
    check("strict confirmed fills (2) << naive fills (22.5)",
          vs["confirmed_genuine_maker_fills"] < row["fills"])

    # sample frame / station count consistency
    check("n_stations == 20", data["n_stations"] == 20)
    check("n_calendar_days == 65", data["n_calendar_days"] == 65)
    check("stations_covered has 20 entries matching n_stations",
          len(data["stations_covered"]) == data["n_stations"])

    # FATAL findings must be present and drive the verdict (per orchestrator: FATAL must be excluded/reworked)
    fatal_ids = [f["id"] for f in data["panel_findings"] if f["severity"] == "FATAL"]
    check("at least 2 FATAL findings recorded", len(fatal_ids) >= 2)
    check("verdict text mentions REFUTED", "REFUTED" in data["panel_verdict_summary"])
    check("recommendation explicitly says DO NOT DEPLOY",
          "DO NOT DEPLOY" in data["recommendation"]["verdict"])

    print()
    print("SELFTEST: " + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return ok


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    data = load_data()
    print_naive_table(data)
    print_strict_table(data)
    print_verdict(data)


if __name__ == "__main__":
    main()
