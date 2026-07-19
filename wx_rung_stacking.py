#!/usr/bin/env python3
"""wx_rung_stacking.py -- is firing the FULL locked_orders() set (vs just the single best-gap rung) worth
the extra order-placement complexity, or is rank-2+ dead weight at 98-99c after fees?

WHY THIS MATTERS: kwx_runner.locked_orders() already returns every rung the observed extreme has
mechanically cleared in one poll -- the marginal (just-crossed) rung PLUS any deeper-ITM rungs still priced
<=MAX_PAY_CENTS, and the mirrored NO-side rungs on the other side of the ladder. poll_once() fires all of
them. Whether that's worth doing is an EMPIRICAL question about real asks and real fees, not a design
opinion: each rung's fill is capacity-bounded by its own book, so "fire everything" only pays off if the
rank-2+ rungs are (a) still net-positive after the exchange fee and (b) not simply cannibalizing the same
liquidity the rank-1 rung would have consumed anyway.

STUDY 1 (trackA historical, deployed cell): group every LIVE-ADMISSIBLE fire (deployed cell "1_3", ask
<=MAX_PAY_CENTS -- same admissibility filter wx_ev_concentration.py and wx_fee_floor_impact.py use, since
99-100c raw "fired" cells are dead-on-arrival and MAX_PAY_CENTS already excludes them live) by (series,
date) -- one "fire event" = one city-market-day's cascade of rung locks. Within each event, rank fired
rungs by gap (=1-exec_price, the edge still open) descending: rank-1 = best-gap rung, rank-2+ = every other
rung that fired the same day on the same series. Compare EV ($/ct, total $, win rate) and capacity
(volume_at_exec, a per-fire depth proxy) between rank-1-only and the full set. A STRICT secondary cut
repeats this using (series, date, t_star) -- literal same-minute-poll simultaneity -- to check the
day-level grouping isn't just aggregating unrelated intraday crossings.

STUDY 2 (live book snapshots): wx_book_snapshots.jsonl near-lock rung rows (yes_ask in [50,98]c) -- how
many rungs per event-sweep pass the near-lock gate simultaneously, and what's the aggregate depth<=98c
across them vs the single best one, at TODAY's real books.

STUDY 3 (NO-side mirror): trackA's `side` field (SHORT = the fired order is a NO buy, LONG = YES buy) lets
us check whether NO-side locked rungs (side=SHORT, the vast majority -- "between"/most "less"/"greater"
crossings) differ materially in gap/EV from the rare LONG (YES) fires.

PROPOSE-ONLY: reads the recorded backtest + committed snapshots, prints numbers. NO parameter or runner
code is touched -- this is evidence for/against a future change, not the change itself.

Usage: python wx_rung_stacking.py
"""
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kwx_runner import MARGIN_F, SUSTAIN_MIN, MAX_PAY_CENTS

RAW = os.path.join(HERE, "_trackA_results_raw.json")
SNAP = os.path.join(HERE, "wx_book_snapshots.jsonl")
DEPLOYED_CELL = f"{int(MARGIN_F)}_{SUSTAIN_MIN}"   # "1_3" -- must match wx_ev_concentration.py / wx_fee_floor_impact.py


def wilson_ci(k, n, z=1.96):
    """Two-sided Wilson score CI for a binomial proportion k/n (same formula as wx_ev_concentration.py)."""
    if n <= 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def load_admissible_fires():
    """Every LIVE-ADMISSIBLE fire (deployed cell, ask <= MAX_PAY_CENTS), one dict per fired rung."""
    raw = json.load(open(RAW))
    fires = []
    for r in raw:
        c = r["cells"].get(DEPLOYED_CELL)
        if not c or not c.get("fired"):
            continue
        ep = c.get("exec_price")
        if ep is None or round(ep * 100) > MAX_PAY_CENTS:
            continue
        fires.append({
            "series": r["series"], "date": r["date"], "city": r["city"], "station": r["station"],
            "ticker": r["ticker"], "family": r["family"], "rung_group": r.get("rung_group", "?"),
            "side": r.get("side", "?"), "t_star": c["t_star"], "gap": c["gap"], "pnl": c["pnl"],
            "win": 1 if c["pnl"] > 0 else 0,
            "volume_at_exec": c.get("volume_at_exec") or 0.0,
        })
    return fires, len(raw)


def _bucket(gap):
    gc = gap * 100
    if gc < 5:
        return "<5c"
    if gc < 15:
        return "5-15c"
    return ">15c"


def _rows_stats(rows):
    n = len(rows)
    tot_pnl = sum(r["pnl"] for r in rows)
    tot_vol = sum(r["volume_at_exec"] for r in rows)
    wins = sum(r["win"] for r in rows)
    lo, hi = wilson_ci(wins, n)
    return {
        "n": n, "total_pnl": tot_pnl, "mean_ct": tot_pnl / n if n else 0.0,
        "total_vol": tot_vol, "win": wins, "win_rate": wins / n if n else 0.0,
        "wilson_lo": lo, "wilson_hi": hi,
    }


def _print_stats(label, s):
    print(f"  {label:<34} n={s['n']:>5}  total_pnl=${s['total_pnl']:>8.2f}  mean/ct=${s['mean_ct']:>7.4f}  "
          f"vol(capacity)={s['total_vol']:>8.0f}  win={s['win']}/{s['n']}={s['win_rate']:.3f}  "
          f"Wilson95=[{s['wilson_lo']:.3f},{s['wilson_hi']:.3f}]")


def rank_split(fires, keyfn):
    """Group fires by keyfn, rank each group by gap descending, split into rank-1 vs rank-2+."""
    groups = defaultdict(list)
    for f in fires:
        groups[keyfn(f)].append(f)
    rank1, rank2p = [], []
    sizes = []
    for v in groups.values():
        v2 = sorted(v, key=lambda x: -x["gap"])
        rank1.append(v2[0])
        rank2p.extend(v2[1:])
        sizes.append(len(v2))
    return groups, rank1, rank2p, sizes


# ---------------------------------------------------------------------------------------------------------
# STUDY 1: trackA rank-1 vs rank-2+
# ---------------------------------------------------------------------------------------------------------
def study1(fires):
    print(f"\n=== STUDY 1: trackA rank-1 vs rank-2+ stacking (deployed cell '{DEPLOYED_CELL}') ===")
    print(f"n live-admissible fires = {len(fires)}\n")

    print("-- primary cut: fire EVENT = (series, date) [one city-market-day] --")
    groups, rank1, rank2p, sizes = rank_split(fires, lambda f: (f["series"], f["date"]))
    size_dist = defaultdict(int)
    for s in sizes:
        size_dist[s] += 1
    print(f"  n events = {len(groups)}; rungs-fired-per-event distribution: "
          + ", ".join(f"{k}x={v}" for k, v in sorted(size_dist.items())))
    n_multi = sum(1 for s in sizes if s > 1)
    print(f"  events with >1 rung fired = {n_multi}/{len(groups)} ({100*n_multi/len(groups):.1f}%)\n")
    s1, s2 = _rows_stats(rank1), _rows_stats(rank2p)
    _print_stats("rank-1 (best gap/event)", s1)
    _print_stats("rank-2+ (rest of the stack)", s2)
    tot_pnl, tot_vol = s1["total_pnl"] + s2["total_pnl"], s1["total_vol"] + s2["total_vol"]
    print(f"\n  if only rank-1 fired: captures ${s1['total_pnl']:.2f}/${tot_pnl:.2f} = "
          f"{100*s1['total_pnl']/tot_pnl:.1f}% of EV, {s1['total_vol']:.0f}/{tot_vol:.0f} = "
          f"{100*s1['total_vol']/tot_vol:.1f}% of capacity")
    print(f"  stacking (rank-2+) adds: {100*s2['total_pnl']/tot_pnl:.1f}% of EV, "
          f"{100*s2['total_vol']/tot_vol:.1f}% of capacity, at mean ${s2['mean_ct']:.4f}/ct "
          f"(vs rank-1's ${s1['mean_ct']:.4f}/ct) and win rate {s2['win_rate']:.3f} "
          f"(Wilson95 [{s2['wilson_lo']:.3f},{s2['wilson_hi']:.3f}])")

    print("\n  -- rank-2+ by gap bucket (is thin-gap rank-2+ actually dead weight after fees?) --")
    for buck in ("<5c", "5-15c", ">15c"):
        sub = [r for r in rank2p if _bucket(r["gap"]) == buck]
        if not sub:
            continue
        s = _rows_stats(sub)
        _print_stats(f"rank-2+ {buck}", s)
    print("  -- rank-1 by gap bucket (for comparison) --")
    for buck in ("<5c", "5-15c", ">15c"):
        sub = [r for r in rank1 if _bucket(r["gap"]) == buck]
        if not sub:
            continue
        s = _rows_stats(sub)
        _print_stats(f"rank-1 {buck}", s)

    print("\n-- strict secondary cut: fire EVENT = (series, date, t_star) [literal same-minute-poll] --")
    _, srank1, srank2p, ssizes = rank_split(fires, lambda f: (f["series"], f["date"], f["t_star"]))
    n_events2 = len(ssizes)
    n_multi2 = sum(1 for s in ssizes if s > 1)
    print(f"  n strict events = {n_events2}; multi-rung (literally simultaneous) = {n_multi2} "
          f"({100*n_multi2/n_events2:.1f}%)")
    ss1, ss2 = _rows_stats(srank1), _rows_stats(srank2p)
    _print_stats("STRICT rank-1", ss1)
    _print_stats("STRICT rank-2+ (literal simultaneous)", ss2)
    tot2 = ss1["total_pnl"] + ss2["total_pnl"]
    print(f"  literal-simultaneous rank-2+ share of EV = {100*ss2['total_pnl']/tot2:.1f}% "
          f"(n={ss2['n']}, mean/ct=${ss2['mean_ct']:.4f}, win={ss2['win_rate']:.3f} "
          f"Wilson95=[{ss2['wilson_lo']:.3f},{ss2['wilson_hi']:.3f}])")
    return {"day_rank1": s1, "day_rank2p": s2, "strict_rank1": ss1, "strict_rank2p": ss2,
            "n_events": len(groups), "n_multi_events": n_multi}


# ---------------------------------------------------------------------------------------------------------
# STUDY 2: live book snapshots -- aggregate near-lock depth per event
# ---------------------------------------------------------------------------------------------------------
def study2():
    print("\n=== STUDY 2: live near-lock book depth (wx_book_snapshots.jsonl) ===")
    if not os.path.exists(SNAP):
        print("  no snapshot file committed -- skipping")
        return None
    rows = [json.loads(l) for l in open(SNAP) if l.strip()]
    print(f"n snapshot rows = {len(rows)}")
    sweeps = defaultdict(list)
    for r in rows:
        sweeps[(r["ts_utc"], r["event_ticker"])].append(r)
    n_sweeps = len({r["ts_utc"] for r in rows})
    print(f"n sweeps = {n_sweeps}; n event-sweep groups = {len(sweeps)}")
    multi = {k: v for k, v in sweeps.items() if len(v) > 1}
    print(f"event-sweeps with >1 near-lock rung simultaneously ask-in-[50,98]c = {len(multi)}/{len(sweeps)}")
    if multi:
        for k, v in multi.items():
            best = max(v, key=lambda r: r["depth_at_or_below_98c"])
            tot_depth = sum(r["depth_at_or_below_98c"] for r in v)
            print(f"  {k}: {len(v)} rungs, best-single depth={best['depth_at_or_below_98c']}, "
                  f"aggregate depth={tot_depth}, multiplier={tot_depth/max(best['depth_at_or_below_98c'],1):.2f}x")
    else:
        print("  NONE in this snapshot set -- with only "
              f"{n_sweeps} sweep(s)/{len(rows)} rows committed, this dataset (unlike trackA's 66-day history) "
              "has not yet caught two rungs on the same event both sitting in the ask-in-[50,98]c near-lock "
              "band at the same sweep. Single-rung-per-event depths still bound what ONE rung can absorb:")
    depths = sorted(r["depth_at_or_below_98c"] for r in rows)
    if depths:
        n = len(depths)
        med = depths[n // 2]
        print(f"  single-rung depth<=98c: min={depths[0]} median={med} max={depths[-1]} "
              f"(n={n}, {sum(1 for d in depths if d == 0)} empty books)")
    return {"n_rows": len(rows), "n_sweeps": n_sweeps, "n_multi_rung_events": len(multi)}


# ---------------------------------------------------------------------------------------------------------
# STUDY 3: NO-side (SHORT) vs YES-side (LONG) mirror
# ---------------------------------------------------------------------------------------------------------
def study3(fires):
    print("\n=== STUDY 3: NO-side (SHORT) vs YES-side (LONG) mirror ===")
    print("(trackA `side`: SHORT = fired order is a NO buy [between/most less/greater cap-crossed], "
          "LONG = fired order is a YES buy [open-ended floor-crossed 'greater'/'less' rung])")
    for side in ("SHORT", "LONG"):
        rows = [f for f in fires if f["side"] == side]
        s = _rows_stats(rows)
        _print_stats(side, s)
    n = len(fires)
    n_short = sum(1 for f in fires if f["side"] == "SHORT")
    print(f"\n  SHORT (NO-side) is {n_short}/{n} = {100*n_short/n:.1f}% of all live-admissible fires -- "
          "i.e. the mechanical-lock mirror the runner already fires on the NO side dominates fire count.")
    # do stacked events mix sides, or fire same-side together?
    groups = defaultdict(list)
    for f in fires:
        groups[(f["series"], f["date"])].append(f)
    multi = [v for v in groups.values() if len(v) > 1]
    mixed = sum(1 for v in multi if len({f["side"] for f in v}) > 1)
    print(f"  of {len(multi)} multi-rung events, {mixed} ({100*mixed/len(multi):.1f}%) mix SHORT+LONG "
          "fires in the same event (i.e. both a NO-side and a YES-side rung locked the same city-day)")


def main():
    fires, n_raw = load_admissible_fires()
    r1 = study1(fires)
    r2 = study2()
    study3(fires)
    print("\n=== summary ===")
    print(f"raw trackA records: {n_raw}; live-admissible fires (cell {DEPLOYED_CELL}): {len(fires)}")


if __name__ == "__main__":
    main()
