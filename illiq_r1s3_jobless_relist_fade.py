#!/usr/bin/env python3
"""
SPEC #3 (pre-registered): JOBLESS-CLAIMS RELIST FADE — KXJOBLESSCLAIMS
Backtest agent. Runs the mechanical procedure EXACTLY as pre-registered, using
real Kalshi public API data cached under ./cache/.

Pre-registered bar (verbatim from task):
  Entry: at first print of each weekly relisting >=24h before Thursday 8:30ET release,
  compute bucket probability from empirical distribution of week-over-week claim
  deltas using settled data <= listing time only; if |first_print - model_p| > theta,
  theta in {15,20}c fit-set only, take model side at print price, taker fee.
  Exit: hold to settlement.
  Fit: first 20 release-weeks; validation: remainder.
  Tradeability guard: entry counts only if a second independent print within +-10c
  occurs the same week; else excluded (stale quote presumption).
  Min n: >=20 validation entries across >=15 distinct release Thursdays, else
  verdict = INCONCLUSIVE (pre-registered escape clause -- not a pass, no goalpost move).
  Adverse-selection check (mandatory): bucket entries by time-to-release
  (>72h / 24-72h / <24h); monotone deterioration of realized edge toward release =
  informed counterparties, FAIL.
  Pass bar: release-Thursday-clustered mean net EV > 0, one-sided p<0.05 Bonferroni x10,
  Wilson 95% lower bound above fee-inclusive breakeven, tradeability + adverse-selection
  checks passed. Honest capacity if passed: $10-40/mo; paper-only sleeve if passed.

DATA-AVAILABILITY FINDING (discovered during harvest, not assumed):
  The pre-registration text assumed "100 settled mkts/47 events" for KXJOBLESSCLAIMS.
  The events list endpoint does show 47 past weekly events (KXJOBLESSCLAIMS-25JUN12
  through -26JUL16) plus 1 currently open. BUT the public markets-list API only
  returns market objects (and therefore trades) for the most recent 10 settled
  events (KXJOBLESSCLAIMS-26MAY14 .. -26JUL16, ~ the last 10 weeks). This was
  confirmed three independent ways:
    1. GET /markets?series_ticker=KXJOBLESSCLAIMS (paginated to cursor exhaustion)
       -> only events from 26MAY14 onward appear.
    2. GET /markets?event_ticker=<event> for each of the other 37 event tickers
       -> markets: [] for every one of them.
    3. GET /events/<event>?with_nested_markets=true for a pre-cutoff event
       -> markets: [] (event metadata exists, market objects do not).
    4. Direct ticker lookup GET /markets/<guessed-ticker> for a pre-cutoff market
       -> 404 not_found. GET /markets/trades?ticker=<same> -> trades: [] (empty,
       not an error -- consistent with the market object never being served).
  This is a hard read of the live API on 2026-07-20, not a script bug (two
  independent query paths agree). Usable n is therefore 10 release weeks, not 47.
"""
import json, math, statistics, datetime as dt
from pathlib import Path

CACHE = Path(__file__).parent / "cache"
OUT = Path(__file__).parent

FEE_RATE = 7  # ceil(7*p*(1-p))/100 dollars, p in [0,1] price of the side traded

def fee_dollars(p):
    return math.ceil(FEE_RATE * p * (1 - p)) / 100.0

def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    phat = k / n
    denom = 1 + z**2 / n
    center = phat + z**2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return (lo, hi)

def parse_claims(s):
    return int(str(s).replace(",", ""))

def event_date(ev_ticker):
    # e.g. KXJOBLESSCLAIMS-26JUL16 -> 2026-07-16
    tag = ev_ticker.split("-")[-1]
    yy = int(tag[0:2])
    mon = tag[2:5]
    dd = int(tag[5:7])
    months = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,"JUL":7,"AUG":8,
              "SEP":9,"OCT":10,"NOV":11,"DEC":12}
    return dt.date(2000 + yy, months[mon], dd)

def load():
    markets = json.load(open(CACHE / "markets_by_event.json"))
    trades = json.load(open(CACHE / "trades_by_ticker.json"))
    return markets, trades

def main():
    markets, trades = load()

    by_event = {}
    for m in markets:
        by_event.setdefault(m["event_ticker"], []).append(m)

    events_sorted = sorted(by_event.keys(), key=event_date)
    actual_by_event = {}
    for e in events_sorted:
        vals = set(parse_claims(m["expiration_value"]) for m in by_event[e])
        assert len(vals) == 1, f"inconsistent expiration_value in {e}: {vals}"
        actual_by_event[e] = vals.pop()

    n_events = len(events_sorted)
    n_distinct_thursdays = len(set(event_date(e) for e in events_sorted))

    # ---- Pre-registered fit/validation split: first 20 release-weeks fit, remainder validation ----
    fit_events = events_sorted[:20]
    val_events = events_sorted[20:]

    availability = {
        "distinct_release_weeks_available": n_events,
        "distinct_thursdays_available": n_distinct_thursdays,
        "events_in_prereg_fit_window_first20": len(fit_events),
        "events_left_for_validation": len(val_events),
        "prereg_min_validation_entries": 20,
        "prereg_min_validation_thursdays": 15,
        "meets_minimum_n_bar": False,
    }

    # Hard pre-registered escape clause: with events_left_for_validation == 0
    # (all 10 weeks consumed by the "first 20" fit window, since n<20), and with
    # total distinct Thursdays (10) already below the 15-Thursday validation
    # minimum even under an alternative split, the spec's own min-n rule fires.
    verdict = "INCONCLUSIVE"

    # ---------------------------------------------------------------
    # EXPLORATORY-ONLY pass below: NOT a hypothesis test, NOT used for
    # pass/fail. Runs the mechanical entry/exit/adverse-selection logic
    # on all 10 weeks with an expanding-window model, purely to check the
    # pipeline is correct and to see directional signal for the record.
    # Theta grid {15,20}c reported both (no valid fit-only selection is
    # possible with a degenerate fit set), tradeability guard and AS
    # checks applied exactly as pre-registered.
    # ---------------------------------------------------------------
    exploratory = {}
    for theta_cents in (15, 20):
        theta = theta_cents / 100.0
        entries = []
        for idx, ev in enumerate(events_sorted):
            hist_events = events_sorted[:idx]  # strictly before this event's listing
            hist_vals = [actual_by_event[e] for e in hist_events]
            deltas = [hist_vals[j+1] - hist_vals[j] for j in range(len(hist_vals) - 1)]
            n_deltas = len(deltas)
            if n_deltas < 1:
                continue  # cannot build ANY empirical distribution
            v_last = hist_vals[-1]
            release_dt = dt.datetime.combine(event_date(ev), dt.time(8, 30)) \
                .replace(tzinfo=dt.timezone(dt.timedelta(hours=-4)))  # ET approx, DST ignored (~1h, immaterial at 24h/72h buckets)

            for m in by_event[ev]:
                ticker = m["ticker"]
                floor_strike = m["floor_strike"]
                result = m["result"]  # 'yes' or 'no'
                tlist = sorted(trades.get(ticker, []), key=lambda t: t["created_time"])
                if not tlist:
                    continue
                first = tlist[0]
                first_ts = dt.datetime.fromisoformat(first["created_time"].replace("Z", "+00:00"))
                hours_to_release = (release_dt.astimezone(dt.timezone.utc) - first_ts).total_seconds() / 3600.0
                if hours_to_release < 24:
                    continue  # pre-registered timing gate

                first_price = float(first["yes_price_dollars"])
                # tradeability guard: a second independent print within +-10c, same week
                guard_ok = False
                for t2 in tlist[1:]:
                    p2 = float(t2["yes_price_dollars"])
                    if abs(p2 - first_price) <= 0.10:
                        guard_ok = True
                        break
                if not guard_ok:
                    continue

                model_p = sum(1 for d in deltas if (v_last + d) >= floor_strike) / n_deltas

                divergence = model_p - first_price
                if abs(divergence) <= theta:
                    continue  # no signal

                side = "yes" if divergence > 0 else "no"
                price_paid = first_price if side == "yes" else (1 - first_price)
                won = (result == side)
                fee = fee_dollars(price_paid)
                net_ev = (1 - price_paid if won else -price_paid) - fee

                entries.append({
                    "event": ev, "ticker": ticker, "release_thursday": str(event_date(ev)),
                    "floor_strike": floor_strike, "n_deltas_in_model": n_deltas,
                    "model_p": round(model_p, 4), "first_print": first_price,
                    "divergence": round(divergence, 4), "side": side,
                    "price_paid": price_paid, "won": won, "fee": fee,
                    "net_ev": round(net_ev, 4), "hours_to_release": round(hours_to_release, 1),
                })

        n = len(entries)
        wins = sum(1 for e in entries if e["won"])
        thursdays = len(set(e["release_thursday"] for e in entries))
        ev_list = [e["net_ev"] for e in entries]
        mean_ev = statistics.mean(ev_list) if ev_list else float('nan')

        # day(release-Thursday)-clustered t-test on net EV
        clusters = {}
        for e in entries:
            clusters.setdefault(e["release_thursday"], []).append(e["net_ev"])
        cluster_means = [statistics.mean(v) for v in clusters.values()]
        if len(cluster_means) >= 2:
            cm_mean = statistics.mean(cluster_means)
            cm_sd = statistics.stdev(cluster_means)
            se = cm_sd / math.sqrt(len(cluster_means)) if cm_sd > 0 else float('nan')
            t_stat = cm_mean / se if se and se == se and se > 0 else float('nan')
        else:
            cm_mean, t_stat = (cluster_means[0] if cluster_means else float('nan')), float('nan')

        wl, wh = wilson_ci(wins, n) if n else (float('nan'), float('nan'))

        # adverse-selection check: bucket by time-to-release
        buckets = {">72h": [], "24-72h": [], "<24h": []}
        for e in entries:
            h = e["hours_to_release"]
            if h > 72:
                buckets[">72h"].append(e["net_ev"])
            elif h >= 24:
                buckets["24-72h"].append(e["net_ev"])
            else:
                buckets["<24h"].append(e["net_ev"])
        bucket_means = {k: (statistics.mean(v) if v else None) for k, v in buckets.items()}

        exploratory[f"theta_{theta_cents}c"] = {
            "n_entries": n,
            "n_distinct_thursdays": thursdays,
            "n_wins": wins,
            "win_rate": round(wins / n, 4) if n else None,
            "wilson95_lo": round(wl, 4) if wl == wl else None,
            "wilson95_hi": round(wh, 4) if wh == wh else None,
            "mean_net_ev_per_contract": round(mean_ev, 4) if mean_ev == mean_ev else None,
            "thursday_clustered_mean": round(cm_mean, 4) if cm_mean == cm_mean else None,
            "thursday_clustered_t": round(t_stat, 3) if t_stat == t_stat else None,
            "adverse_selection_bucket_means_by_time_to_release": {
                k: (round(v, 4) if v is not None else None) for k, v in bucket_means.items()
            },
            "entries_detail": entries,
        }

    result = {
        "spec": "3 - jobless-claims relist fade",
        "series": "KXJOBLESSCLAIMS",
        "run_date": "2026-07-20",
        "data_availability_finding": {
            "prereg_assumption": "100 settled mkts / 47 events",
            "actual_events_listed_by_events_endpoint": 47,
            "actual_events_with_queryable_market_objects": n_events,
            "actual_markets_with_queryable_market_objects": sum(len(v) for v in by_event.values()),
            "cutoff": "only events from KXJOBLESSCLAIMS-26MAY14 onward return market objects/trades; "
                      "37 older events (26MAY07 back through 25JUN12) return empty market lists AND "
                      "404 on direct ticker lookup, confirmed via 3 independent query paths",
        },
        "prereg_fit_validation_split": availability,
        "verdict": verdict,
        "verdict_reason": (
            f"Only {n_events} distinct release weeks ({n_distinct_thursdays} distinct Thursdays) "
            "are reachable via the public API, against a pre-registered floor of >=20 validation "
            "entries across >=15 distinct release Thursdays (with the first 20 weeks reserved for "
            "fit). Even a maximally generous re-split (0 fit weeks, all weeks to validation) tops "
            f"out at {n_distinct_thursdays} distinct Thursdays, still short of the 15-Thursday floor. "
            "This is the pre-registered escape clause firing, not a goalpost move: verdict is "
            "INCONCLUSIVE, not a pass and not a fail."
        ),
        "exploratory_only_not_a_test": exploratory,
    }

    with open(OUT / "results.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    # ---- results.md ----
    lines = []
    lines.append("# SPEC #3 — Jobless-Claims Relist Fade — Backtest Result\n")
    lines.append(f"**Run date:** 2026-07-20  **Series:** KXJOBLESSCLAIMS\n")
    lines.append("## VERDICT: INCONCLUSIVE (pre-registered escape clause, not a pass, not a fail)\n")
    lines.append(result["verdict_reason"] + "\n")
    lines.append("## Data-availability finding (the actual story)\n")
    da = result["data_availability_finding"]
    lines.append(f"- Pre-registration assumed **100 settled markets / 47 events**.")
    lines.append(f"- `/events?series_ticker=KXJOBLESSCLAIMS` really does list **47** past weekly events "
                  f"(2025-06-12 through 2026-07-16) plus 1 currently open.")
    lines.append(f"- But the public **markets-list / trades API only serves the most recent "
                  f"{da['actual_events_with_queryable_market_objects']} of those events** "
                  f"({da['actual_markets_with_queryable_market_objects']} markets, 2026-05-14 onward). "
                  f"The other 37 events return `markets: []` from both the series-level and "
                  f"event_ticker-filtered listing endpoints, `markets: []` from "
                  f"`/events/<ticker>?with_nested_markets=true`, and a flat `404 not_found` when a "
                  f"market ticker for that week is queried directly. Confirmed via 4 independent "
                  f"calls, not a script bug.")
    lines.append(f"- Net effect: **n = 10 usable release weeks**, not 47. This is the single biggest "
                  f"reason a real backtest cannot be run here, and it is a *data-availability* wall, "
                  f"not a code bug or a modeling failure.\n")
    lines.append("## Pre-registered minimum-n check\n")
    lines.append(f"- Distinct release weeks reachable: **{n_events}**")
    lines.append(f"- Distinct release Thursdays reachable: **{n_distinct_thursdays}**")
    lines.append(f"- Pre-registered fit window (first 20 weeks) would consume all {n_events} available "
                  f"weeks, leaving **0 validation entries** — automatically below the required "
                  f"≥20 validation entries / ≥15 distinct Thursdays bar.")
    lines.append(f"- Even the most generous alternative split (skip fit entirely, use every week as "
                  f"validation) still only reaches {n_distinct_thursdays} distinct Thursdays — still "
                  f"short of the 15-Thursday floor.")
    lines.append(f"- **Per pre-registration this is an automatic INCONCLUSIVE. No fit/validation "
                  f"stats, no Bonferroni-corrected p-value, and no capacity estimate can legitimately "
                  f"be computed on this sample.**\n")
    lines.append("## Exploratory-only run (NOT a hypothesis test — for the record only)\n")
    lines.append("To confirm the mechanical pipeline (entry rule, tradeability guard, fee model, "
                  "adverse-selection buckets) is implemented correctly and to see directional signal, "
                  "the full procedure was still run across all 10 available weeks with an "
                  "expanding-window empirical-delta model. This is explicitly **not** a validated "
                  "result — n is far below the pre-registered floor, and theta was NOT selected on "
                  "an independent fit set (there isn't one), so both grid values are reported "
                  "descriptively:\n")
    for k, v in exploratory.items():
        lines.append(f"### {k}")
        lines.append(f"- n entries (after timing gate + tradeability guard): **{v['n_entries']}** "
                      f"across **{v['n_distinct_thursdays']}** distinct Thursdays")
        if v['n_entries']:
            lines.append(f"- win rate: {v['win_rate']} (Wilson 95% CI [{v['wilson95_lo']}, {v['wilson95_hi']}])")
            lines.append(f"- mean net EV/contract (fee-inclusive): {v['mean_net_ev_per_contract']}")
            lines.append(f"- Thursday-clustered mean: {v['thursday_clustered_mean']}, "
                          f"t = {v['thursday_clustered_t']} (n={v['n_distinct_thursdays']} clusters — "
                          f"not a meaningful t-test at this n)")
            lines.append(f"- adverse-selection bucket means by time-to-release: "
                          f"{v['adverse_selection_bucket_means_by_time_to_release']}")
        else:
            lines.append("- no entries survived the timing gate + tradeability guard at this theta")
        lines.append("")
    lines.append("## Headline numbers (as requested)\n")
    best = exploratory.get("theta_15c", {})
    n_ = best.get("n_entries", 0)
    lines.append(f"- **n (exploratory, theta=15c):** {n_} entries / {best.get('n_distinct_thursdays',0)} Thursdays "
                 f"— below pre-registered minimum, so treat as descriptive only")
    if n_:
        lines.append(f"- **win rate:** {best['win_rate']}")
        lines.append(f"- **EV/contract net of fee:** {best['mean_net_ev_per_contract']}")
        lines.append(f"- **Wilson 95% CI (win rate):** [{best['wilson95_lo']}, {best['wilson95_hi']}]")
        lines.append(f"- **Thursday-clustered t-stat:** {best['thursday_clustered_t']} "
                     f"(uninterpretable — {best['n_distinct_thursdays']} clusters)")
    lines.append(f"- **Realistic capacity: $0/mo tradeable today.** There is not enough settled/queryable "
                 f"history on this series to certify an edge, so nothing should be deployed, paper or "
                 f"otherwise, until either (a) more weeks accumulate live to reach the pre-registered "
                 f"n-floor, or (b) Kalshi's historical data API is confirmed to expose the pre-2026-05-14 "
                 f"weeks through some other endpoint.\n")
    lines.append("## What worries me most\n")
    lines.append(
        "The 37 \"missing\" events are not randomly missing — they include the Oct 2025 government "
        "shutdown gap (no DOL releases, no jobless-claims markets for ~9 weeks) sitting right in the "
        "middle of the window. If earlier-history access is ever restored (a different endpoint, "
        "an authenticated tier, etc.), naively concatenating pre- and post-shutdown claims to build "
        "the week-over-week delta distribution would silently splice a real macro regime break into "
        "the model as if it were noise. Anyone resuming this spec later needs to explicitly exclude "
        "the shutdown-adjacent weeks from the delta history, not just paper over the gap in the date "
        "index. Second-order concern: even the 10 weeks we *do* have are unusually eventful for "
        "jobless claims (visible level swings of 15-20k between adjacent prints in the exploratory "
        "table above) — that is exactly the kind of regime where a market maker with a same-day DOL "
        "feed prices fast and a lagging empirical-delta model gets picked off, so even a favorable-"
        "looking exploratory EV number here should not be trusted as representative of calmer weeks."
    )

    with open(OUT / "results.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps({
        "verdict": verdict,
        "n_events_available": n_events,
        "n_distinct_thursdays": n_distinct_thursdays,
        "exploratory": {k: {kk: vv for kk, vv in v.items() if kk != "entries_detail"} for k, v in exploratory.items()},
    }, indent=2, default=str))

if __name__ == "__main__":
    main()
