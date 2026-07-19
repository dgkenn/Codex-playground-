#!/usr/bin/env python3
"""wx_ev_concentration.py -- WHERE does the deployed cell's EV actually live, and is the correlated-day
tail risk the sizing caps assume for real? Two cheap, data-local studies on _trackA_results_raw.json.

WHY THIS MATTERS: kwx_runner spends real money and real polling budget everywhere equally today (Synoptic
HF-ASOS is a paid Tier-2 upgrade being evaluated for a subset of cities -- see synoptic_feed.py). If most of
the deployed cell's profit is concentrated in a handful of cities/hours/rungs, that's where a faster feed
(or more polling budget, or Synoptic credentialing priority) pays for itself first; the rest is low-value
real estate. Separately, the bankroll caps (kwx_runner.MAX_DAILY_DEPLOY_FRAC=60% and PER_CITY_DAILY_CAP_FRAC
=17.5%, both marked "precautionary" in kwx_runner.py) were set from a Monte-Carlo sizing study
(kwx_sizing.py), not from the recorded correlated-fire pattern -- this checks whether the recorded pattern
of same-day / same-city fire clustering is consistent with those caps' implicit assumptions.

STUDY A (EV concentration map): for the deployed cell's LIVE-ADMISSIBLE fires (ask <= 98c, i.e. the fires
the runner actually would have paid for -- MAX_PAY_CENTS already kills 99c/100c dead-on-arrival fires, and
crediting those to this study would be double-counting an existing control), break down count / mean pnl-
per-contract / total pnl / win rate by city, local fire hour, family, rung group, and gap bucket. Also use
decay_gap_by_min to measure, PER CITY, how much of the profit gap survives to t=+2min -- the cities where it
evaporates fastest are the ones a slow (hourly METAR) feed hurts most and a 1-min feed (Synoptic) helps most.

STUDY B (correlated-day tail): same-day and same-city-day fire-count distributions, the worst joint-pnl
days, and Wilson-CI'd empirical P(fire-count > K) -- checked against what the 60%-daily / 17.5%-per-city
caps implicitly assume about how much can pile up in one day. EVIDENCE ONLY: this script proposes no
parameter change (see the "no param change without supporting evidence" rule used throughout this repo,
e.g. wx_fee_floor_impact.py) -- it just reports whether the caps look adequate, too loose, or too tight
against the recorded clustering.

PROPOSE-ONLY: reads the recorded backtest file, prints numbers, writes nothing. Never trades.

Usage: python wx_ev_concentration.py
"""
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# Pull the deployed cell id, the city->(station,UTC-offset) map, and the live bankroll caps straight from
# the production runner (not private copies) so this analysis tracks whatever is ACTUALLY deployed.
from kwx_runner import CITY, MARGIN_F, SUSTAIN_MIN, MAX_PAY_CENTS, MAX_DAILY_DEPLOY_FRAC, PER_CITY_DAILY_CAP_FRAC

RAW = os.path.join(HERE, "_trackA_results_raw.json")
DEPLOYED_CELL = f"{int(MARGIN_F)}_{SUSTAIN_MIN}"          # "1_3" -- must match wx_fee_floor_impact.py
LAG_MINUTES = [0, 1, 2, 5, 10]
# station -> fixed STANDARD-time UTC offset (never DST; see kwx_runner.CITY comment). LOW markets settle on
# the same LST calendar day/station as their matching HIGH, so keying by station (not series) sidesteps the
# HIGH/LOW series-naming mess entirely and is exhaustive: every station in CITY.values() is unique (checked).
STATION_OFFSET = {station: off for station, off in CITY.values()}
assert len(STATION_OFFSET) == len(CITY), "station->offset map assumed 1:1; CITY no longer unique per station"


def wilson_ci(k, n, z=1.96):
    """Two-sided Wilson score CI for a binomial proportion k/n at confidence implied by z (1.96 -> 95%).
    Same formula as kalshi_weather_nowcast.wilson_upper_bound but returns both bounds -- Study B needs the
    full interval, not just the conservative upper edge."""
    if n <= 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def load_admissible_fires():
    """Every LIVE-ADMISSIBLE fire (deployed cell, ask <= MAX_PAY_CENTS) with the fields both studies need.
    RAW fired cells also include 99c/100c dead-on-arrival fires that MAX_PAY_CENTS already excludes live
    (wx_fee_floor_impact.py: 2347/3891 raw fires are exactly this, all pnl=0) -- keeping them here would
    dilute every mean and inflate 'city concentration' with zero-EV noise the runner never actually pays
    for, so both studies use the same LIVE-ADMISSIBLE definition wx_fee_floor_impact.py uses."""
    raw = json.load(open(RAW))
    fires = []
    for r in raw:
        c = r["cells"].get(DEPLOYED_CELL)
        if not c or not c.get("fired"):
            continue
        price_c = round(c["exec_price"] * 100)
        if price_c > MAX_PAY_CENTS:
            continue
        off = STATION_OFFSET[r["station"]]
        utc_hour = int(c["t_star"][11:13])
        fires.append({
            "date": r["date"], "city": r["city"], "station": r["station"],
            "family": r["family"], "rung": r.get("rung_group", "?"),
            "pnl": c["pnl"], "win": 1 if c["outcome"] == 1.0 else 0,
            "gap": c["gap"], "local_hour": (utc_hour + off) % 24,
            "decay": {int(k): v for k, v in (c.get("decay_gap_by_min") or {}).items() if v is not None},
        })
    return fires, len(raw)


# ---------------------------------------------------------------------------------------------------------
# STUDY A: EV concentration map
# ---------------------------------------------------------------------------------------------------------

def _breakdown(fires, total_pnl, keyfn):
    grp = defaultdict(list)
    for f in fires:
        grp[keyfn(f)].append(f)
    rows = []
    for k, v in grp.items():
        tot = sum(f["pnl"] for f in v)
        rows.append({
            "key": k, "n": len(v), "mean_ct": tot / len(v), "total": tot,
            "win_rate": sum(f["win"] for f in v) / len(v),
            "share_pct": 100.0 * tot / total_pnl if total_pnl else 0.0,
        })
    rows.sort(key=lambda r: -r["total"])
    return rows


def _print_breakdown(title, rows, key_width=10, key_fmt=str):
    print(f"\n--- {title} ---")
    print(f"{'':>{key_width}}{'n':>6}{'mean/ct':>10}{'total$':>10}{'win%':>7}{'shareEV':>9}")
    cum = 0.0
    for r in rows:
        cum += r["share_pct"]
        print(f"{key_fmt(r['key']):>{key_width}}{r['n']:>6}{r['mean_ct']:>+10.4f}{r['total']:>+10.2f}"
              f"{100*r['win_rate']:>6.1f}%{r['share_pct']:>8.1f}%")
    print(f"{'':>{key_width}}{'':>6}{'':>10}{'cumulative through table:':>10}{cum:>15.1f}%")


def _gap_bucket(g):
    if g < 0.05:
        return "<5c"
    if g < 0.15:
        return "5-15c"
    return ">15c"


def study_a(fires):
    total_pnl = sum(f["pnl"] for f in fires)
    print(f"\n{'='*95}\nSTUDY A -- EV concentration map | deployed cell {DEPLOYED_CELL} | "
          f"{len(fires)} live-admissible fires (ask<={MAX_PAY_CENTS}c) | total pnl ${total_pnl:.2f}")

    by_city = _breakdown(fires, total_pnl, lambda f: f["station"])
    _print_breakdown("by city/station (sorted by total $ EV, descending)", by_city)
    top5_share = sum(r["share_pct"] for r in by_city[:5])
    print(f"\n  top 5 of {len(by_city)} stations = {top5_share:.1f}% of total EV")

    by_hour = sorted(_breakdown(fires, total_pnl, lambda f: f["local_hour"]), key=lambda r: r["key"])
    _print_breakdown("by LOCAL fire hour (station standard-time)", by_hour, key_width=6)

    by_family = _breakdown(fires, total_pnl, lambda f: f["family"])
    _print_breakdown("by family", by_family)

    by_rung = _breakdown(fires, total_pnl, lambda f: f["rung"])
    _print_breakdown("by rung_group", by_rung)

    by_gap = sorted(_breakdown(fires, total_pnl, lambda f: _gap_bucket(f["gap"])),
                     key=lambda r: {"<5c": 0, "5-15c": 1, ">15c": 2}[r["key"]])
    _print_breakdown("by gap bucket", by_gap)

    # --- latency: per-city EV survival to +2/+5/+10 min, both as a RATE (retention -- who decays fastest
    # per fire) and as ABSOLUTE $ (who has the most money riding on beating the lag -- priority for a fast
    # feed is the intersection of "decays fast" AND "has real volume", so both views are reported). Fires
    # with essentially zero gap(0) are excluded here (nothing to lose to latency, not a decay signal).
    print(f"\n--- per-city EV lost to detection lag (decay_gap_by_min; excludes ~0-gap fires) ---")
    decay_rows = []
    for station in {f["station"] for f in fires}:
        ds = [f["decay"] for f in fires if f["station"] == station and f["decay"].get(0, 0.0) >= 0.01]
        if not ds:
            continue
        g0 = sum(d.get(0, 0.0) for d in ds)
        retained = {t: sum(d.get(t, 0.0) for d in ds) / g0 for t in LAG_MINUTES}
        lost2_dollars = g0 - sum(d.get(2, 0.0) for d in ds)
        decay_rows.append((station, len(ds), g0, retained, lost2_dollars))
    total_lost2 = sum(r[4] for r in decay_rows)

    print(f"{'stn':>6}{'n':>5}{'gap0$':>8}{'ret@2':>8}{'ret@5':>8}{'ret@10':>8}{'lost@2$':>9}{'share':>8}")
    for station, n, g0, ret, lost2 in sorted(decay_rows, key=lambda r: -r[3][2]):
        print(f"{station:>6}{n:>5}{g0:>8.2f}{ret[2]:>8.2f}{ret[5]:>8.2f}{ret[10]:>8.2f}{lost2:>9.2f}"
              f"{100*lost2/total_lost2 if total_lost2 else 0:>7.1f}%")
    print(f"\n  (sorted by ret@2 ascending = fastest decay first; 'lost@2$' = absolute $ of gap gone by "
          f"+2min, the $-priority view for where a faster feed pays off most)")
    by_abs_loss = sorted(decay_rows, key=lambda r: -r[4])
    top_abs = [r[0] for r in by_abs_loss[:7]]
    cum_share = sum(r[4] for r in by_abs_loss[:7]) / total_lost2 * 100 if total_lost2 else 0
    print(f"  top 7 by ABSOLUTE $ lost to 2-min lag: {top_abs} = {cum_share:.1f}% of all lag-driven $ loss")
    return by_city, decay_rows


# ---------------------------------------------------------------------------------------------------------
# STUDY B: correlated-day tail
# ---------------------------------------------------------------------------------------------------------

def study_b(fires, n_raw_records):
    print(f"\n{'='*95}\nSTUDY B -- correlated-day tail | deployed cell {DEPLOYED_CELL}")

    all_dates = sorted({f["date"] for f in fires})
    # anchor on the full backtest's calendar span (not just fire-days) so zero-fire days count toward the
    # denominator -- otherwise P(fires/day > K) would be conditioned on "a day with at least one fire",
    # silently dropping the (rare) quiet days and overstating how clustered a typical day is.
    raw_dates = sorted({r["date"] for r in json.load(open(RAW))})
    n_days = len(raw_dates)

    by_date = defaultdict(list)
    for f in fires:
        by_date[f["date"]].append(f)
    fires_per_day = {d: len(by_date.get(d, [])) for d in raw_dates}
    cities_per_day = {d: len({f["station"] for f in by_date.get(d, [])}) for d in raw_dates}

    fvals = list(fires_per_day.values())
    cvals = list(cities_per_day.values())
    print(f"\n{n_days} calendar days in backtest span ({raw_dates[0]}..{raw_dates[-1]})")
    print(f"fires/day        : min={min(fvals)} median={sorted(fvals)[len(fvals)//2]} "
          f"mean={sum(fvals)/len(fvals):.1f} max={max(fvals)}")
    print(f"distinct cities/day: min={min(cvals)} median={sorted(cvals)[len(cvals)//2]} "
          f"mean={sum(cvals)/len(cvals):.1f} max={max(cvals)} (of {len(CITY)} total)")

    print(f"\nempirical P(fires/day > K), Wilson 95% CI, n={n_days} days:")
    for K in (5, 10, 12, 15, 20, 25, 30):
        k = sum(1 for v in fvals if v > K)
        lo, hi = wilson_ci(k, n_days)
        print(f"  K={K:>3}: {k:>3}/{n_days} = {100*k/n_days:5.1f}%   [{100*lo:5.1f}%, {100*hi:5.1f}%]")

    # --- worst joint-pnl days (does correlated same-day risk ever show up as a net daily loss?) ---
    day_rows = []
    for d in raw_dates:
        v = by_date.get(d, [])
        if not v:
            continue
        day_rows.append({
            "date": d, "n": len(v), "n_cities": len({f["station"] for f in v}),
            "pnl": sum(f["pnl"] for f in v), "n_losses": sum(1 for f in v if not f["win"]),
        })
    day_rows.sort(key=lambda r: r["pnl"])
    print(f"\n--- 10 worst joint-pnl days (deployed cell, live-admissible) ---")
    print(f"{'date':>12}{'n_fires':>9}{'n_cities':>10}{'day_pnl$':>10}{'n_losses':>10}")
    for r in day_rows[:10]:
        print(f"{r['date']:>12}{r['n']:>9}{r['n_cities']:>10}{r['pnl']:>+10.3f}{r['n_losses']:>10}")
    net_loss_days = sum(1 for r in day_rows if r["pnl"] < 0)
    multi_loss_days = sum(1 for r in day_rows if r["n_losses"] > 1)
    print(f"\n  net-pnl-negative days: {net_loss_days}/{len(day_rows)}   "
          f"days with >1 losing fire (any city): {multi_loss_days}/{len(day_rows)}")

    # --- per-city-day stacking (multiple rungs firing the SAME city SAME day are correlated -- same
    # underlying temperature draw at different strikes -- which is exactly what PER_CITY_DAILY_CAP_FRAC
    # is meant to bound) ---
    city_date_counts = defaultdict(int)
    for f in fires:
        city_date_counts[(f["date"], f["station"])] += 1
    cd_vals = list(city_date_counts.values())
    n_cd = len(cd_vals)
    print(f"\n--- per-city-day fire stacking (same city, same day; n={n_cd} city-days with >=1 fire) ---")
    for K in (1, 2, 3, 4):
        k = sum(1 for v in cd_vals if v > K)
        lo, hi = wilson_ci(k, n_cd)
        print(f"  P(city fires > {K}x same day) = {k:>3}/{n_cd} = {100*k/n_cd:5.1f}%   "
              f"[{100*lo:5.1f}%, {100*hi:5.1f}%]")

    # --- compare against the caps' IMPLICIT assumption: if every fire were sized at its cap (5% base /
    # 12% conviction -- the worst case, since Kelly at the recorded ~99.6% win rate saturates the cap on
    # almost every fire per kwx_runner._kelly_fraction, so "sized at cap" is not a hypothetical extreme,
    # it's close to the realistic case), how many same-day / same-city fires would it take to BREACH each
    # cap? This is arithmetic on the caps, not a new statistical claim -- reported for comparison only.
    base_cap, conv_cap = 0.05, 0.12
    breach_daily_base = math.ceil(MAX_DAILY_DEPLOY_FRAC / base_cap)      # fires/day to hit 60% at 5% each
    breach_city_base = math.ceil(PER_CITY_DAILY_CAP_FRAC / base_cap)     # fires/city-day to hit 17.5% at 5%
    breach_city_conv = math.ceil(PER_CITY_DAILY_CAP_FRAC / conv_cap)     # fires/city-day to hit 17.5% at 12%
    print(f"\n--- cap arithmetic (worst-case: every fire sized at its cap) ---")
    print(f"  MAX_DAILY_DEPLOY_FRAC={MAX_DAILY_DEPLOY_FRAC:.0%} would need >{breach_daily_base} same-day "
          f"fires at base {base_cap:.0%} cap to breach; observed median fires/day = "
          f"{sorted(fvals)[len(fvals)//2]}, P(fires/day > {breach_daily_base-1}) shown above")
    print(f"  PER_CITY_DAILY_CAP_FRAC={PER_CITY_DAILY_CAP_FRAC:.0%} would need >{breach_city_base} same-city-"
          f"day fires at base {base_cap:.0%} cap (or >{breach_city_conv} at conviction {conv_cap:.0%} cap) "
          f"to breach; observed rates shown above")
    return day_rows, cd_vals


def main():
    fires, n_raw = load_admissible_fires()
    by_city, decay_rows = study_a(fires)
    study_b(fires, n_raw)


if __name__ == "__main__":
    main()
