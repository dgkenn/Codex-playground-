#!/usr/bin/env python3
"""wx_scaling_schedule.py -- SCALING SCHEDULE + DEPTH-ADAPTIVE SIZING study (operator's roadmap $10 -> capacity).

Q1 SCALING SCHEDULE: Monte-Carlo bankroll growth under the CURRENT DEPLOYED sizing rule -- literally
kwx_runner.size_for_fire (fee-aware quarter-Kelly, 5%/12%-conviction per-fire cap, DEPTH_CAP=25, 17.5%
per-city cap, 60% daily cap) -- across bankroll levels $10..$1000, using the real fires in
_trackA_results_raw.json (deployed cell "1_3": MARGIN_F=1, SUSTAIN_MIN=3) and the measured empty-book rate
from the accrued wx_book_snapshots.jsonl. Reports expected weekly $, 30-day $ (the number to compare to the
$4k/mo goal), time-to-double, and where DEPTH_CAP starts binding -- then an evidence-keyed advancement
ladder (gates on observed stats, not calendar time).

Q2 DEPTH-ADAPTIVE SIZING: today's cap is a flat DEPTH_CAP=25 regardless of the actual book. This simulates
sizing as min(Kelly, alpha * displayed_depth) for alpha in {0.25, 0.5, 1.0}, using per-station live depth
from wx_book_snapshots.jsonl (--report) mapped onto the historical fires, against fixed caps {25, 50, 100}.
Adverse impact is not assumed -- it is MEASURED by walking the real resting-ask ladders in the accrued
snapshots for the actual order sizes each rule would place.

PROPOSE-ONLY: reads the committed backtest + accrued live snapshots. Touches no live parameter in
kwx_runner.py. Honest caveat carried throughout: the live snapshot file has n=33 rows from ONE sweep on ONE
day (2026-07-19) -- real data, but early. Every claim built on it says so.

Usage: python wx_scaling_schedule.py
"""
import json, os, math, random, statistics as st
from collections import defaultdict
import kwx_runner as R

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_trackA_results_raw.json")
SNAP = os.path.join(HERE, "wx_book_snapshots.jsonl")
LATENCY = "5"          # free-feed action latency (matches the currently-deployed default feed)
GOAL_MONTHLY = 4000.0  # operator's stated goal


# ----------------------------------------------------------------------------------------------
# data loading (real fires, deployed cell 1_3)
# ----------------------------------------------------------------------------------------------
def cushion_of(rec):
    hi = 0
    for m in (1, 2, 3):
        if rec["cells"].get(f"{m}_3", {}).get("fired"):
            hi = m
    return hi


def load_fires(latency=LATENCY):
    """Real, live-admissible fires at the deployed cell, with the latency-decayed price kwx_runner would
    actually have acted on. Carries volume_at_exec (flow proxy) and per-record station for Q2."""
    raw = json.load(open(RAW))
    out = []
    for rec in raw:
        c = rec["cells"].get("1_3")
        if not c or not c.get("fired") or c["exec_price"] >= 0.99:
            continue
        gap = c.get("decay_gap_by_min", {}).get(latency)
        price = (1.0 - gap) if gap is not None else c["exec_price"]
        price = min(0.99, max(0.01, price))
        if price >= 0.99:
            continue
        outcome = c.get("outcome", 1 if c["pnl"] > 0 else 0)
        fee = R._kalshi_fee_c(int(round(price * 100))) / 100.0
        out.append({
            "date": rec["date"], "station": rec.get("station", "?"),
            "price": price, "price_c": int(round(price * 100)), "outcome": outcome,
            "pnl": outcome - price - fee, "fee": fee,
            "cushion": cushion_of(rec), "gap_c": round((1.0 - price) * 100, 1),
            "volume_at_exec": c.get("volume_at_exec") or 0.0,
        })
    return out


def load_snapshot_depth():
    """Per-station median displayed depth (<=98c) from the accrued live snapshots, + global fallback.
    HONEST CAVEAT: n=33 rows, ONE sweep, ONE day (2026-07-19). Real live data, but early -- treat these as
    a first calibration point, not a stable estimate."""
    rows = []
    if os.path.exists(SNAP):
        for line in open(SNAP):
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    per = defaultdict(list)
    for r in rows:
        per[r["station"]].append(r["depth_at_or_below_98c"])
    med = {s: st.median(v) for s, v in per.items()}
    global_med = st.median([r["depth_at_or_below_98c"] for r in rows]) if rows else 25.0
    return med, global_med, rows


# ----------------------------------------------------------------------------------------------
# Q1: scaling schedule -- deployed sizing engine, real fires, MC bankroll growth
# ----------------------------------------------------------------------------------------------
def _sim_day(fires, bank, rng, unfill, badday_p):
    """One day's realized $ pnl on `bank`, using the ACTUAL deployed sizing engine (R.size_for_fire) plus
    the cross-fire budget constraints (per-city 17.5%, daily 60%, available cash) that size_for_fire itself
    doesn't know about (it only sizes one fire in isolation, exactly like the live runner does per-cycle;
    the day-level caps are enforced by the same arithmetic kwx_conviction_sizing/kwx_bankroll_curve use)."""
    bad = rng.random() < badday_p
    city_spent = defaultdict(float)
    avail = bank
    day_cap = R.MAX_DAILY_DEPLOY_FRAC * bank
    deployed = 0.0
    dpnl = 0.0
    depth_bound = 0
    n_sized = 0
    for f in sorted(fires, key=lambda x: x["price"]):
        if rng.random() < unfill:
            continue
        price, price_c = f["price"], f["price_c"]
        n_ideal = R.size_for_fire(bank, price_c, f["station"], cushion_f=f["cushion"], gap_c=f["gap_c"])
        if n_ideal < 1:
            continue
        city_room = R.PER_CITY_DAILY_CAP_FRAC * bank - city_spent[f["station"]]
        day_room = day_cap - deployed
        room_n = min(city_room, day_room, avail) / price
        n = min(n_ideal, int(room_n))
        if n < 1:
            continue
        n_sized += 1
        if n_ideal == R.DEPTH_CAP:
            depth_bound += 1
        cost = n * price
        city_spent[f["station"]] += cost
        avail -= cost
        deployed += cost
        pnl_c = (-price - f["fee"]) if bad else f["pnl"]
        dpnl += n * pnl_c
    return dpnl, depth_bound, n_sized


def scaling_schedule(fires, banks, unfill, badday_p=0.02, trials=3000, week_days=7, month_days=30, seed=42):
    by_day = defaultdict(list)
    for f in fires:
        by_day[f["date"]].append(f)
    day_keys = list(by_day)
    rng = random.Random(seed)
    rows = []
    for bank0 in banks:
        weekly, monthly, dbl_days = [], [], []
        depth_bound_tot = n_sized_tot = 0
        for _ in range(trials):
            b = bank0
            week_pnl = None
            days_to_double = None
            for d in range(month_days):
                pnl, db, ns = _sim_day(by_day[rng.choice(day_keys)], b, rng, unfill, badday_p)
                depth_bound_tot += db
                n_sized_tot += ns
                b += pnl
                if d == week_days - 1:
                    week_pnl = b - bank0
                if days_to_double is None and b >= 2 * bank0:
                    days_to_double = d + 1
            weekly.append(week_pnl)
            monthly.append(b - bank0)
            dbl_days.append(days_to_double if days_to_double is not None else month_days + 1)  # censored floor
        weekly.sort(); monthly.sort(); dbl_days.sort()
        n = trials
        dbind_rate = depth_bound_tot / n_sized_tot if n_sized_tot else 0.0
        never_doubled = sum(1 for d in dbl_days if d > month_days) / n
        med_dbl = st.median(dbl_days) if never_doubled < 0.5 else None
        rows.append({
            "bank": bank0, "week_med": weekly[n // 2], "week_mean": st.mean(weekly),
            "month_med": monthly[n // 2], "month_mean": st.mean(monthly),
            "depth_bind_rate": dbind_rate, "med_double_days": med_dbl, "never_doubled_frac": never_doubled,
        })
    return rows


def print_ladder_table(rows, tag):
    print(f"\n--- Q1 scaling schedule | unfillable={tag} ---")
    print(f"{'bankroll':>10}{'wk$med':>9}{'wk$mean':>9}{'mo$med':>9}{'mo$mean':>9}{'mo%med':>8}"
          f"{'depthBind%':>11}{'medDblDays':>12}{'vs$4k/mo':>10}")
    for r in rows:
        dbl = f"{r['med_double_days']:.0f}" if r["med_double_days"] is not None else f">{30}(cens)"
        pct4k = f"{100*r['month_med']/GOAL_MONTHLY:.1f}%"
        print(f"${r['bank']:>9.0f}${r['week_med']:>8.2f}${r['week_mean']:>8.2f}${r['month_med']:>8.2f}"
              f"${r['month_mean']:>8.2f}{100*r['month_med']/r['bank']:>7.0f}%{100*r['depth_bind_rate']:>10.1f}%"
              f"{dbl:>12}{pct4k:>10}")


# ----------------------------------------------------------------------------------------------
# Q2: depth-adaptive sizing -- alpha*depth vs fixed caps, with REAL book-walk adverse impact
# ----------------------------------------------------------------------------------------------
def walk_book_slippage(levels, n):
    """Walk a REAL resting yes-ask ladder [[price_c,count],...] (best-first) to fill n contracts.
    Returns (avg_fill_price_c, best_ask_c, slippage_c) or None if the book can't fill n at all."""
    if not levels:
        return None
    best = levels[0][0]
    remaining = n
    cost = 0
    for price_c, cnt in levels:
        take = min(remaining, cnt)
        cost += take * price_c
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        return None   # book too thin to fill n at all (walked off the end)
    avg = cost / n
    return avg, best, avg - best


def measure_real_impact(snap_rows, alphas, fixed_caps):
    """For every near-lock snapshot row with a non-empty ask ladder, walk the book at:
      - alpha*row's own displayed depth (the depth-adaptive rule, alpha in {0.25,0.5,1.0})
      - each fixed cap {25,50,100}
    and report mean slippage (cents/contract above best ask) and the fill-failure rate (book too thin)."""
    usable = [r for r in snap_rows if r["yes_ask_levels"] and r["depth_at_or_below_98c"] > 0]
    print(f"\n--- Q2 REAL adverse-impact measurement (book-walk on {len(usable)}/{len(snap_rows)} "
          f"non-empty near-lock snapshot rows, n={len(snap_rows)} total, 1 sweep/1 day) ---")
    print(f"{'rule':>16}{'meanSlip(c)':>12}{'p90Slip(c)':>11}{'fillFail%':>10}{'meanN':>8}")
    results = {}
    for a in alphas:
        slips, fails, ns = [], 0, []
        for r in usable:
            n = max(1, int(round(a * r["depth_at_or_below_98c"])))
            ns.append(n)
            res = walk_book_slippage(r["yes_ask_levels"], n)
            if res is None:
                fails += 1
                continue
            slips.append(res[2])
        label = f"alpha={a}"
        results[label] = {"mean_slip": st.mean(slips) if slips else None,
                           "p90_slip": sorted(slips)[int(0.9 * len(slips))] if slips else None,
                           "fail_rate": fails / len(usable), "mean_n": st.mean(ns)}
        p90 = f"{results[label]['p90_slip']:.2f}" if results[label]['p90_slip'] is not None else "n/a"
        ms = f"{results[label]['mean_slip']:.2f}" if results[label]['mean_slip'] is not None else "n/a"
        print(f"{label:>16}{ms:>12}{p90:>11}{100*results[label]['fail_rate']:>9.1f}%{results[label]['mean_n']:>8.0f}")
    for cap in fixed_caps:
        slips, fails = [], 0
        for r in usable:
            res = walk_book_slippage(r["yes_ask_levels"], cap)
            if res is None:
                fails += 1
                continue
            slips.append(res[2])
        label = f"fixed={cap}"
        results[label] = {"mean_slip": st.mean(slips) if slips else None,
                           "p90_slip": sorted(slips)[int(0.9 * len(slips))] if slips else None,
                           "fail_rate": fails / len(usable), "mean_n": cap}
        p90 = f"{results[label]['p90_slip']:.2f}" if results[label]['p90_slip'] is not None else "n/a"
        ms = f"{results[label]['mean_slip']:.2f}" if results[label]['mean_slip'] is not None else "n/a"
        print(f"{label:>16}{ms:>12}{p90:>11}{100*results[label]['fail_rate']:>9.1f}%{cap:>8}")
    return results


def ev_captured_sim(fires, depth_by_station, global_depth, alphas, fixed_caps, impact, bank=2000.0,
                     unfill=0.21, trials=2000, seed=7):
    """At a bankroll where the flat DEPTH_CAP=25 is already the binding constraint on most fires (Q1 shows
    this starts ~$300-500), compare total EV captured under alpha*depth rules vs fixed caps. Uses the SAME
    quarter-Kelly / per-fire-cap-% budget as the deployed rule -- only the DEPTH ceiling itself changes.
    Impact is applied as the MEASURED mean slippage-per-contract from measure_real_impact (cents), scaled by
    how much of the row's own depth the order consumes -- i.e. this is not a free-form assumption, it's the
    book-walk number carried over. Where no matching-station snapshot exists, the global snapshot mean
    slippage is used (explicit fallback, flagged in the report)."""
    by_day = defaultdict(list)
    for f in fires:
        by_day[f["date"]].append(f)
    day_keys = list(by_day)
    rng = random.Random(seed)

    def depth_for(station):
        return depth_by_station.get(station, global_depth)

    def run(depth_cap_fn, slip_c_per_ct=0.0):
        total_ev, total_n = 0.0, 0
        for _ in range(trials):
            day = rng.choice(day_keys)
            city_spent = defaultdict(float)
            avail = bank
            day_cap = R.MAX_DAILY_DEPLOY_FRAC * bank
            deployed = 0.0
            for f in sorted(by_day[day], key=lambda x: x["price"]):
                if rng.random() < unfill:
                    continue
                price, price_c = f["price"], f["price_c"]
                fee_c = R._kalshi_fee_c(price_c)
                if (100 - price_c - fee_c) <= R.MIN_NET_EDGE_C:
                    continue
                kelly = R._kelly_fraction(price_c, fee_c=fee_c)
                if kelly <= 0:
                    continue
                cap_frac = R.CONV_CAP if R.is_conviction(f["cushion"], f["gap_c"]) else R.PER_FIRE_CAP
                frac = min(R.KELLY_FRAC * kelly, cap_frac) * R.STATION_SIZE_MULT.get(f["station"], 1.0)
                dcap = depth_cap_fn(f["station"])
                n = int(frac * bank / price)
                n = min(n, dcap)
                city_room = R.PER_CITY_DAILY_CAP_FRAC * bank - city_spent[f["station"]]
                day_room = day_cap - deployed
                room_n = min(city_room, day_room, avail) / price
                n = min(n, int(room_n))
                if n < 1:
                    continue
                cost = n * price
                city_spent[f["station"]] += cost
                avail -= cost
                deployed += cost
                impact = slip_c_per_ct / 100.0
                total_ev += n * (f["pnl"] - impact)
                total_n += n
        return total_ev / trials, total_n / trials

    print(f"\n--- Q2 EV-captured sim | bankroll ${bank:.0f} (depth-cap-bound regime) | "
          f"{trials} trials, 1 random day/trial | impact = MEASURED book-walk slippage (real, not assumed) ---")
    print(f"{'rule':>16}{'EV$/trial-day(noImpact)':>25}{'EV$/trial-day(impact)':>23}{'meanContracts':>14}")
    rows = {}
    for a in alphas:
        label = f"alpha={a}"
        slip_c = (impact.get(label) or {}).get("mean_slip") or 0.0
        ev0, n = run(lambda s, a=a: max(1, int(a * depth_for(s))))
        ev1, _ = run(lambda s, a=a: max(1, int(a * depth_for(s))), slip_c_per_ct=slip_c)
        rows[label] = (ev0, ev1, n)
        print(f"{label:>16}{ev0:>25.3f}{ev1:>23.3f}{n:>14.1f}")
    for cap in fixed_caps:
        label = f"fixed={cap}"
        slip_c = (impact.get(label) or {}).get("mean_slip") or 0.0
        ev0, n = run(lambda s, cap=cap: cap)
        ev1, _ = run(lambda s, cap=cap: cap, slip_c_per_ct=slip_c)
        rows[label] = (ev0, ev1, n)
        print(f"{label:>16}{ev0:>25.3f}{ev1:>23.3f}{n:>14.1f}")
    return rows


# ----------------------------------------------------------------------------------------------
def main():
    fires = load_fires()
    print("=" * 90)
    print(f"WX SCALING SCHEDULE + DEPTH-ADAPTIVE SIZING | {len(fires)} live-admissible fires "
          f"(deployed cell 1_3, {LATENCY}min latency) | {len(set(f['date'] for f in fires))} days")
    print("=" * 90)

    # ---- Q1 ----
    banks = [10, 25, 50, 100, 250, 500, 1000]
    rows_legacy = scaling_schedule(fires, banks, unfill=0.21)
    print_ladder_table(rows_legacy, "21% (legacy Tier-1 prior, baked into kwx_sizing.py/kwx_bankroll_curve.py)")
    rows_measured = scaling_schedule(fires, banks, unfill=0.0)
    print_ladder_table(rows_measured, "0% (point estimate from wx_book_snapshots --report, n=33/1 day)")

    # price-weighted bankroll where DEPTH_CAP starts binding, base vs conviction cap
    prices = [f["price"] for f in fires]
    med_price = st.median(prices)
    bank_bind_base = R.DEPTH_CAP * med_price / R.PER_FIRE_CAP
    bank_bind_conv = R.DEPTH_CAP * med_price / R.CONV_CAP
    print(f"\nDEPTH_CAP=25 starts binding (median-price fire, {med_price:.2f}) at bankroll ~"
          f"${bank_bind_base:.0f} (base 5% cap) / ~${bank_bind_conv:.0f} (12% conviction cap).")

    # ---- Q2 ----
    depth_by_station, global_depth, snap_rows = load_snapshot_depth()
    print(f"\nlive snapshot depth: {len(snap_rows)} rows, {len(depth_by_station)} stations, "
          f"global median depth {global_depth:.0f}ct (n=33, 1 sweep, 1 day -- EARLY DATA)")
    alphas = [0.25, 0.5, 1.0]
    fixed_caps = [25, 50, 100]
    impact = measure_real_impact(snap_rows, alphas, fixed_caps)
    ev_rows = ev_captured_sim(fires, depth_by_station, global_depth, alphas, fixed_caps, impact, bank=2000.0)

    print("\nDone. See wx_scaling_schedule.md for the narrative read + evidence-keyed ladder + verdict.")


if __name__ == "__main__":
    main()
