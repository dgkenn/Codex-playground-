#!/usr/bin/env python3
"""per_market_champion.py -- is the global shadow champion (av_stoikov) the best arm on EVERY
Kalshi 15m crypto asset, or does btc/eth/sol/xrp each want a different arm?

Reuses per_asset_edge.py's git-native gha-data access (one `git cat-file --batch` over the
shadow_windows_kalshi_<asset>15m_* blobs, no working-tree checkout of the multi-GB gha_data
tree) -- see that file's module docstring for why. This script differs in scope: per_asset_edge
only ever compared the two declared 32-day winners (av_stoikov, mo_size) to baseline. This one
ranks EVERY arm present in the data, per asset, and then asks the harder question: does any
arm's OWN asset-level edge over av_stoikov (not over baseline) clear a bar strict enough to
justify running something other than the global champion on that market.

=====================================================================================
SELECTION DISCIPLINE -- read this BEFORE looking at any numbers below (pre-registered).
=====================================================================================
The repo's own history is a catalogue of lab winners that died forward (strategies.py's PRUNED
block: micro_strict, lead30, ufat_band, micro_cal ... every one of them looked great on an
in-sample scoring cut and then lost money live). The roster here has ~22 non-baseline arms
across 4 assets = ~88 (asset, arm) cells. Picking each asset's argmax cell is a multiple-
comparisons fishing expedition: with that many cells, SOME arm will look like a big winner on
SOME asset by chance alone, exactly the failure mode this repo keeps re-discovering.

The rule (fixed here, before the table below was ever printed):

    An asset is assigned a TAILORED champion (something other than av_stoikov) if, and ONLY if,
    ALL of the following hold for that (asset, arm) pair, using the PAIRED PER-DAY delta of
    (arm's window net) MINUS (av_stoikov's window net) on THAT asset -- i.e. head-to-head
    against the champion it would replace, not against baseline:

      1. day-clustered t-stat  >= TAILOR_T_BAR   (3.0)
      2. days-positive fraction >= TAILOR_DAYS_POS_BAR (0.70)
      3. n_days of head-to-head data >= MIN_DAYS_EVAL (10) -- a t-stat computed on a handful of
         days is exactly how the pruned arms got their initial (fake) lab wins; this bar is the
         same "need enough day-observations" floor per_asset_edge.py uses (MIN_DAYS=10).

    Fail any of the three -> that asset's champion DEFAULTS to av_stoikov, full stop, no
    exceptions for "but the mean delta looked good."

This is deliberately stricter than the vs-baseline promotion bar in strategies.py (t>=2,
days+>=60%) because here we are proposing to REPLACE an already-validated month-long winner,
not just clear baseline -- the bar for dethroning a champion should be higher than the bar for
beating the null.

Consequence stated up front: arms added in the 2026-07-11 evening roster change (as_markout,
mo_skew99, skew99, as_cap100, as_k_half, as_k_2x, mo_k_half, mo_k_2x, as_resv, as_spread,
queue_gate, late_boost, vol_size, xnet) have at most ~1-2 days of data as of this run. They
CANNOT clear MIN_DAYS_EVAL=10 by construction -- this script says so explicitly per asset rather
than silently omitting them, and they remain on strategies.py's own pre-registered forward-track
bar (>=14 forward days, t>=3, gross-positive >=80% of days) until they accumulate enough days to
even be looked at here.

    python per_market_champion.py                 # fetches gha-data fresh
    python per_market_champion.py --ref <sha>      # reuse an already-fetched ref
"""
from __future__ import annotations

import argparse
import sys

from per_asset_edge import (
    ASSETS,
    BASE,
    fetch_ref,
    load_windows,
    _mean,
    _day_tstat,
    _utc_date,
)

GLOBAL_CHAMPION = "av_stoikov"

# Roster change boundary (evidence, not used in the math -- see module docstring). Arms whose
# data starts on/after this date are the ~18-arm post-change roster; everything else is the
# ~25-arm era. We don't special-case dates anywhere below: arms are discovered purely from the
# keys present in each row, and a new arm's small n_days falls straight out of that.
ROSTER_CHANGE_DATE = "2026-07-11"

# --- Task 1 (full ranked table) display/evaluability bar -- NOT the selection-discipline bar,
# just "enough data to print a day-t at all" (matches per_asset_edge.py's own floor).
MIN_DAYS_EVAL = 10

# --- Task 2 (selection discipline) bar -- pre-registered above, restated here as constants so
# the code and the comment can't drift apart.
TAILOR_T_BAR = 3.0
TAILOR_DAYS_POS_BAR = 0.70


def build_asset_data(by_ws: dict) -> dict[str, list[tuple[int, dict]]]:
    """asset -> [(ws, slot), ...] restricted to windows where baseline resolved (matches
    per_asset_edge.py's convention so the tools agree on the denominator)."""
    windows_by_asset: dict[str, list] = {}
    for (asset, _tenor, ws), slot in by_ws.items():
        windows_by_asset.setdefault(asset, []).append((ws, slot))
    out = {}
    for asset, wins in windows_by_asset.items():
        out[asset] = [(ws, s) for ws, s in wins if BASE in s]
    return out


def arm_names_for_asset(wins: list[tuple[int, dict]]) -> list[str]:
    names: set[str] = set()
    for _ws, slot in wins:
        names.update(slot.keys())
    names.discard(BASE)
    return sorted(names)


def vs_baseline_stats(wins: list[tuple[int, dict]], arm: str) -> dict:
    """(arm net) - (baseline net), paired per window, day-clustered."""
    pairs = [(ws, s[arm][0] - s[BASE][0]) for ws, s in wins if arm in s]
    abs_nets = [s[arm][0] for ws, s in wins if arm in s]
    fills = [s[arm][1] for ws, s in wins if arm in s]
    day_deltas: dict[str, list] = {}
    for ws, d in pairs:
        day_deltas.setdefault(_utc_date(ws), []).append(d)
    day_means = {d: _mean(xs) for d, xs in day_deltas.items()}
    mean_d, t_d, pos_d, n_days = _day_tstat(day_means)
    dates = sorted(day_means.keys())
    return {
        "n": len(pairs),
        "n_days": n_days,
        "first_day": dates[0] if dates else None,
        "last_day": dates[-1] if dates else None,
        "mean_delta": _mean([d for _, d in pairs]),
        "day_mean_delta": mean_d,
        "day_t": t_d,
        "days_pos": pos_d,
        "abs_net_per_win": _mean(abs_nets),
        "mean_fills": _mean(fills),
    }


def head_to_head_stats(wins: list[tuple[int, dict]], arm: str, champion: str = GLOBAL_CHAMPION) -> dict:
    """(arm net) - (champion net), paired per window on days both ran, day-clustered."""
    pairs = [(ws, s[arm][0] - s[champion][0]) for ws, s in wins if arm in s and champion in s]
    day_deltas: dict[str, list] = {}
    for ws, d in pairs:
        day_deltas.setdefault(_utc_date(ws), []).append(d)
    day_means = {d: _mean(xs) for d, xs in day_deltas.items()}
    mean_d, t_d, pos_d, n_days = _day_tstat(day_means)
    dates = sorted(day_means.keys())
    return {
        "n": len(pairs),
        "n_days": n_days,
        "first_day": dates[0] if dates else None,
        "last_day": dates[-1] if dates else None,
        "mean_delta": _mean([d for _, d in pairs]),
        "day_mean_delta": mean_d,
        "day_t": t_d,
        "days_pos": pos_d,
        "days_pos_frac": (pos_d / n_days) if n_days else float("nan"),
    }


def per_asset_ranked_table(asset_data: dict) -> dict[str, list[tuple[str, dict]]]:
    """asset -> [(arm, vs_baseline_stats), ...] sorted by day_t desc (nan last)."""
    out = {}
    for asset in ASSETS:
        wins = asset_data.get(asset, [])
        arms = arm_names_for_asset(wins)
        rows = [(arm, vs_baseline_stats(wins, arm)) for arm in arms]

        def sort_key(item):
            t = item[1]["day_t"]
            return (t == t, t)  # False (nan) sorts before True (real number) -> reverse below

        rows.sort(key=sort_key, reverse=True)
        out[asset] = rows
    return out


def selection_discipline(asset_data: dict, ranked: dict) -> dict:
    """asset -> {champion, champion_reason, runnerup, runnerup_stats, candidates: [...],
    unevaluable_new_arms: [...]}"""
    out = {}
    for asset in ASSETS:
        wins = asset_data.get(asset, [])
        arms = [a for a, _ in ranked[asset] if a != GLOBAL_CHAMPION]
        candidates = []
        unevaluable = []
        for arm in arms:
            h2h = head_to_head_stats(wins, arm, GLOBAL_CHAMPION)
            row = {"arm": arm, **h2h}
            if h2h["n_days"] < MIN_DAYS_EVAL:
                row["status"] = "insufficient-data"
                unevaluable.append(row)
                continue
            t_ok = h2h["day_t"] == h2h["day_t"] and h2h["day_t"] >= TAILOR_T_BAR
            days_ok = h2h["days_pos_frac"] == h2h["days_pos_frac"] and h2h["days_pos_frac"] >= TAILOR_DAYS_POS_BAR
            row["status"] = "CLEARS" if (t_ok and days_ok) else "fails-bar"
            candidates.append(row)

        evaluated = [c for c in candidates if c["status"] != "insufficient-data"]
        clearing = [c for c in evaluated if c["status"] == "CLEARS"]
        evaluated.sort(key=lambda r: (r["day_t"] == r["day_t"], r["day_t"]), reverse=True)

        if clearing:
            clearing.sort(key=lambda r: (r["day_t"], r["mean_delta"]), reverse=True)
            champion = clearing[0]["arm"]
            champion_reason = (
                f"{champion} beats {GLOBAL_CHAMPION} head-to-head: day-t={clearing[0]['day_t']:+.2f} "
                f"(>= {TAILOR_T_BAR:g}), days+={clearing[0]['days_pos']}/{clearing[0]['n_days']} "
                f"({clearing[0]['days_pos_frac']:.0%} >= {TAILOR_DAYS_POS_BAR:.0%}), "
                f"mean delta={clearing[0]['mean_delta']:+.3f}/win -- TAILORED champion"
            )
        else:
            champion = GLOBAL_CHAMPION
            if evaluated:
                best = evaluated[0]
                champion_reason = (
                    f"no arm cleared the tailoring bar (best challenger {best['arm']}: "
                    f"day-t={best['day_t']:+.2f}, days+={best['days_pos']}/{best['n_days']}"
                    f"={best['days_pos_frac']:.0%}) -- default to {GLOBAL_CHAMPION} (global champion)"
                )
            else:
                champion_reason = f"no evaluable challengers (>={MIN_DAYS_EVAL}d head-to-head data) -- default to {GLOBAL_CHAMPION}"

        runnerup = None
        for r in evaluated:
            if r["arm"] != champion:
                runnerup = r
                break

        out[asset] = {
            "champion": champion,
            "champion_reason": champion_reason,
            "runnerup": runnerup,
            "clearing": clearing,
            "evaluated": evaluated,
            "unevaluable_new_arms": unevaluable,
        }
    return out


def _fmt_t(t):
    return f"{t:+.2f}" if t == t else "n/a"


def print_ranked_table(asset: str, rows: list[tuple[str, dict]]):
    hdr = (f"{'arm':>14} {'n win':>6} {'n days':>7} {'mean Δ/win':>11} {'day-t':>7} "
           f"{'days+':>8} {'ABS net/win':>12} {'mean fills':>11}  span")
    print(hdr)
    for arm, a in rows:
        dt = _fmt_t(a["day_t"])
        dp = f"{a['days_pos']}/{a['n_days']}" if a["n_days"] else "0/0"
        span = f"{a['first_day']}..{a['last_day']}" if a["first_day"] else "-"
        flag = " *new-roster*" if a["n_days"] and a["n_days"] < MIN_DAYS_EVAL else ""
        print(f"{arm:>14} {a['n']:>6} {a['n_days']:>7} {a['mean_delta']:>+11.3f} {dt:>7} "
              f"{dp:>8} {a['abs_net_per_win']:>+12.3f} {a['mean_fills']:>11.2f}  {span}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=None, help="reuse an already-fetched gha-data ref (skips the fetch)")
    args = ap.parse_args()

    ref = args.ref or fetch_ref()
    print(f"gha-data ref: {ref}")
    by_ws = load_windows(ref)
    if not by_ws:
        print("no shadow windows found -- aborting.")
        sys.exit(1)
    n_days_total = len({_utc_date(ws) for (_a, _t, ws) in by_ws.keys()})
    print(f"{len(by_ws)} de-duped windows across {n_days_total} UTC days, assets={ASSETS}")
    print(f"global champion under test: {GLOBAL_CHAMPION}\n")

    asset_data = build_asset_data(by_ws)
    ranked = per_asset_ranked_table(asset_data)
    disc = selection_discipline(asset_data, ranked)

    print("=" * 100)
    print("TASK 1 -- per-asset ranked table, every (asset, arm) vs baseline (paired per-window delta,")
    print("day-clustered; sorted by day-t desc). *new-roster* = <10 days of data (2026-07-11 roster change).")
    print("=" * 100)
    for asset in ASSETS:
        print(f"\n--- {asset.upper()} ---  (n_windows_baseline_resolved={len(asset_data.get(asset, []))})")
        print_ranked_table(asset, ranked[asset])

    print("\n" + "=" * 100)
    print(f"TASK 2 -- selection discipline: tailored champion requires head-to-head vs {GLOBAL_CHAMPION} "
          f"day-t>={TAILOR_T_BAR:g} AND days+>={TAILOR_DAYS_POS_BAR:.0%} AND n_days>={MIN_DAYS_EVAL} "
          "(else default to global champion)")
    print("=" * 100)
    for asset in ASSETS:
        d = disc[asset]
        print(f"\n--- {asset.upper()} ---")
        print(f"  CHAMPION: {d['champion']}")
        print(f"    reason: {d['champion_reason']}")
        if d["runnerup"] is not None:
            r = d["runnerup"]
            print(f"  RUNNER-UP: {r['arm']}  (day-t={_fmt_t(r['day_t'])}, "
                  f"days+={r['days_pos']}/{r['n_days']}={r['days_pos_frac']:.0%}, "
                  f"mean delta={r['mean_delta']:+.3f}/win vs {GLOBAL_CHAMPION}, status={r['status']})")
        else:
            print("  RUNNER-UP: none evaluable")
        if d["clearing"] and len(d["clearing"]) > 1:
            print("  (other arms that ALSO cleared the bar, not selected as champion:)")
            for c in d["clearing"][1:]:
                print(f"    - {c['arm']}: day-t={_fmt_t(c['day_t'])}, days+={c['days_pos']}/{c['n_days']}")
        if d["unevaluable_new_arms"]:
            names = ", ".join(sorted(r["arm"] for r in d["unevaluable_new_arms"]))
            print(f"  NOT YET EVALUABLE (new-roster, <{MIN_DAYS_EVAL}d head-to-head data -- stay on the "
                  f"standard forward-promotion track, strategies.py's own pre-registered bar):")
            print(f"    {names}")

    print("\nRead: 'mean Δ/win' / day-t / days+ in Task 1 are vs BASELINE (the no-gate control). Task 2's "
          "day-t / days+ are vs AV_STOIKOV (the arm being challenged for the champion slot) -- a "
          "different, harder comparison on purpose. 'ABS net/win' is the arm's own mean $ net per "
          "window (not vs anything) -- a level check, same trap per_asset_edge.py flags: an arm can "
          "beat baseline while still being net-negative outright.")
    return disc, ranked, asset_data


if __name__ == "__main__":
    main()
