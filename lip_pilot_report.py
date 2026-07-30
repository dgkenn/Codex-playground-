#!/usr/bin/env python3
"""lip_pilot_report.py -- renders M1/M2/M3 and the F1/F2/F3 falsifier states for LIP_PILOT.

Reads lip_pilot_log.jsonl (every place/amend/cancel/fill/snapshot/payout-check event lip_quoter.py
appends) and lip_payouts.jsonl (manual or API-scraped daily payout records -- schema:
{"date": "YYYY-MM-DD", "payout_usd": <float>, ...}, one line per day or per market-day). Pure
read-only analysis: never touches the network, never writes anything but stdout (or the --out file
if given).

Metrics (definitions frozen in venue_expansion/LIP_PILOT_REGISTRATION.md 'Objective'):
  M1: $ payout per day per unit of (size x distance x uptime) -- calibrates score share + discount curve
  M2: fill rate on resting orders as a function of distance from touch
  M3: realized per-fill P&L (settlement-inclusive, fee-inclusive) vs the -8.81c/ct pessimistic bound

Falsifiers (frozen; any one => kill the LIP line):
  F1: first full week's payout < realized fill losses + $2
  F2: payouts ~= $0 at ALL ladder distances (discount factor zeroes off-touch presence)
  F3: program lapses 2026-09-01 without a successor

Usage:
    python lip_pilot_report.py                       # print a text report
    python lip_pilot_report.py --out report.txt       # also write to a file
"""
import argparse
import datetime as dt
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(HERE, "lip_pilot_log.jsonl")
PAYOUTS_FILE = os.path.join(HERE, "lip_payouts.jsonl")
MARKETS_FILE = os.path.join(HERE, "lip_markets.json")

PROGRAM_END_DATE = dt.date(2026, 9, 1)   # LIP_PILOT_REGISTRATION.md: program window ends 2026-09-01
F1_WEEK_DAYS = 7
F1_SLACK_USD = 2.00                       # "< realized fill losses + $2"
F2_ZERO_THRESHOLD_USD = 0.01              # "~= $0.00" -- anything below one cent/day is treated as zero
SUCCESS_BAR_USD_PER_DAY = 1.00
SUCCESS_BAR_USD_PER_MONTH = 30.00
MAKER_VIABILITY_PESSIMISTIC_CPT = -8.81   # cents/contract, from MAKER_VIABILITY.md


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def parse_ts(ts):
    try:
        return dt.datetime.strptime(ts.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=dt.timezone.utc)
    except Exception:
        try:
            return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None


def day0(events, cfg):
    if cfg and cfg.get("day0_date"):
        try:
            return dt.date.fromisoformat(cfg["day0_date"])
        except Exception:
            pass
    tss = [parse_ts(e.get("ts")) for e in events if e.get("ts")]
    tss = [t for t in tss if t is not None]
    if not tss:
        return None
    return min(tss).date()


def load_markets_cfg():
    if not os.path.exists(MARKETS_FILE):
        return {}
    try:
        with open(MARKETS_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {}


# ---------------------------------------------------------------------------------------------
# M1: $ payout / day / (size x distance x uptime)
# ---------------------------------------------------------------------------------------------
def compute_uptime_seconds_by_distance(events):
    """Approximate uptime per (ticker, side, distance_cents) as the wall-clock span between a
    'place'/'place_dry_run' event for that rung and the next 'cancel'/'decrease'/'kill' touching
    the same order_id or client_order_id, summed across all such spans. Coarse (leg-gap blind
    spots are real -- see LIP_PILOT_REGISTRATION.md deployment note) but directionally right and
    entirely derivable from the committed log, with no assumptions about exchange-side presence
    scoring internals (unpublished, per the registration)."""
    opens = {}     # key -> open ts
    spans = {}     # key -> total seconds
    keys_meta = {}  # key -> (ticker, side, distance)

    def key_for(e):
        cid = e.get("client_order_id")
        if cid:
            return cid
        return e.get("order_id")

    for e in sorted(events, key=lambda e: e.get("ts", "")):
        kind = e.get("event")
        ts = parse_ts(e.get("ts"))
        if ts is None:
            continue
        if kind in ("place", "place_dry_run"):
            k = key_for(e)
            opens[k] = ts
            keys_meta[k] = (e.get("ticker"), e.get("side"), e.get("distance_cents"))
        elif kind in ("cancel", "cancel_dry_run", "decrease", "decrease_dry_run", "kill", "batch_cancel"):
            k = key_for(e)
            if k in opens:
                spans[k] = spans.get(k, 0.0) + (ts - opens[k]).total_seconds()
                del opens[k]
    # anything still open counts uptime up to "now" (still resting as of report time)
    now = dt.datetime.now(dt.timezone.utc)
    for k, opened_ts in opens.items():
        spans[k] = spans.get(k, 0.0) + (now - opened_ts).total_seconds()

    by_distance = {}
    for k, secs in spans.items():
        _, _, distance = keys_meta.get(k, (None, None, None))
        if distance is None:
            continue
        by_distance.setdefault(distance, 0.0)
        by_distance[distance] += secs
    return by_distance


def compute_m1(events, payouts, size_ct=1):
    uptime_by_distance = compute_uptime_seconds_by_distance(events)
    total_uptime_days = sum(uptime_by_distance.values()) / 86400.0
    total_payout = sum(p.get("payout_usd", 0.0) for p in payouts)
    n_days = len({p.get("date") for p in payouts if p.get("date")}) or None

    rows = []
    for distance, secs in sorted(uptime_by_distance.items()):
        uptime_days = secs / 86400.0
        denom = size_ct * distance * uptime_days
        # per-distance payout isn't separable without a payout schema that tags distance -- report
        # the aggregate M1 and flag per-distance $/unit as "n/a" unless lip_payouts.jsonl tags
        # "distance_cents" on individual rows (operator/API-scrape dependent).
        per_distance_payout = sum(
            p.get("payout_usd", 0.0) for p in payouts if p.get("distance_cents") == distance
        )
        m1 = (per_distance_payout / denom) if denom > 0 and per_distance_payout else None
        rows.append({
            "distance_cents": distance, "uptime_days": round(uptime_days, 3),
            "payout_usd": round(per_distance_payout, 4), "m1_usd_per_unit": m1,
        })

    aggregate_denom = size_ct * total_uptime_days * (statistics.mean(uptime_by_distance.keys())
                                                       if uptime_by_distance else 0)
    m1_aggregate = (total_payout / aggregate_denom) if aggregate_denom > 0 else None
    return {
        "rows": rows,
        "total_payout_usd": round(total_payout, 4),
        "total_uptime_days": round(total_uptime_days, 3),
        "n_payout_days": n_days,
        "m1_aggregate_usd_per_unit": m1_aggregate,
    }


# ---------------------------------------------------------------------------------------------
# M2: fill rate on resting orders as a function of distance from touch
# ---------------------------------------------------------------------------------------------
def compute_m2(events):
    placed_by_distance = {}
    for e in events:
        if e.get("event") in ("place", "place_dry_run"):
            d = e.get("distance_cents")
            if d is None:
                continue
            placed_by_distance[d] = placed_by_distance.get(d, 0) + 1

    # fills are logged as per-market position deltas (see lip_quoter.detect_and_log_fills), which
    # do NOT carry a distance tag (the exchange fill event schema wasn't confirmable offline -- see
    # KalshiClient's PORTFOLIO SCHEMA NOTE). We can report total fills, but per-distance fill RATE
    # needs either a live-confirmed fills-by-order-id feed or the operator tagging fills manually
    # in lip_payouts.jsonl / a future lip_fills.jsonl. Report what's derivable, flag the rest.
    n_fills = sum(1 for e in events if e.get("event") == "fill")
    n_placed_total = sum(placed_by_distance.values())
    overall_rate = (n_fills / n_placed_total) if n_placed_total else None

    rows = [{"distance_cents": d, "orders_placed": n, "fill_rate": "n/a (needs per-fill distance tag)"}
            for d, n in sorted(placed_by_distance.items())]
    return {"rows": rows, "n_fills_total": n_fills, "n_placed_total": n_placed_total,
            "overall_fill_rate": overall_rate}


# ---------------------------------------------------------------------------------------------
# M3: realized per-fill P&L vs the -8.81c/ct pessimistic bound
# ---------------------------------------------------------------------------------------------
def compute_m3(events):
    fills = [e for e in events if e.get("event") == "fill"]
    total_fill_contracts = sum(abs(e.get("position_delta", 0)) for e in fills)
    snaps = [e for e in events if e.get("event") == "snapshot" and "total_realized_pnl_cents" in e]
    realized_pnl_cents = snaps[-1]["total_realized_pnl_cents"] if snaps else None
    per_fill_cpt = None
    if realized_pnl_cents is not None and total_fill_contracts:
        per_fill_cpt = realized_pnl_cents / total_fill_contracts
    beats_pessimistic_bound = (per_fill_cpt is not None and per_fill_cpt > MAKER_VIABILITY_PESSIMISTIC_CPT)
    return {
        "n_fills": len(fills),
        "total_fill_contracts": total_fill_contracts,
        "realized_pnl_cents": realized_pnl_cents,
        "per_fill_cents_per_contract": per_fill_cpt,
        "pessimistic_bound_cents_per_contract": MAKER_VIABILITY_PESSIMISTIC_CPT,
        "beats_pessimistic_bound": beats_pessimistic_bound,
    }


# ---------------------------------------------------------------------------------------------
# Falsifiers
# ---------------------------------------------------------------------------------------------
def payouts_by_date(payouts):
    out = {}
    for p in payouts:
        d = p.get("date")
        if not d:
            continue
        out[d] = out.get(d, 0.0) + p.get("payout_usd", 0.0)
    return out


def realized_fill_losses_usd(events, since_date=None):
    """Sum of negative realized-pnl deltas between consecutive snapshots (a loss, in dollars),
    optionally restricted to snapshots on/after since_date (YYYY-MM-DD)."""
    snaps = sorted(
        [e for e in events if e.get("event") == "snapshot" and "total_realized_pnl_cents" in e],
        key=lambda e: e.get("ts", ""),
    )
    if since_date:
        snaps = [s for s in snaps if str(s.get("ts", "")) >= since_date]
    loss_cents = 0
    for a, b in zip(snaps, snaps[1:]):
        delta = b["total_realized_pnl_cents"] - a["total_realized_pnl_cents"]
        if delta < 0:
            loss_cents += -delta
    return loss_cents / 100.0


def evaluate_f1(events, payouts, d0):
    if d0 is None:
        return {"state": "PENDING", "detail": "no events yet"}
    week_end = d0 + dt.timedelta(days=F1_WEEK_DAYS)
    today = dt.date.today()
    if today < week_end:
        return {"state": "PENDING", "detail": f"first full week ends {week_end.isoformat()}"}
    pod = payouts_by_date(payouts)
    week_payout = sum(v for k, v in pod.items() if d0.isoformat() <= k < week_end.isoformat())
    week_losses = realized_fill_losses_usd(events, since_date=d0.isoformat())
    threshold = week_losses + F1_SLACK_USD
    triggered = week_payout < threshold
    return {
        "state": "TRIGGERED (KILL)" if triggered else "CLEAR",
        "week_payout_usd": round(week_payout, 2),
        "week_realized_fill_losses_usd": round(week_losses, 2),
        "threshold_usd": round(threshold, 2),
        "detail": f"payout ${week_payout:.2f} vs losses+${F1_SLACK_USD:.2f} = ${threshold:.2f}",
    }


def evaluate_f2(m1_result, payouts):
    if not payouts:
        return {"state": "PENDING", "detail": "no payout data recorded yet"}
    per_distance_totals = {}
    for row in m1_result["rows"]:
        per_distance_totals[row["distance_cents"]] = row["payout_usd"]
    if not per_distance_totals:
        total = sum(p.get("payout_usd", 0.0) for p in payouts)
        all_zero = total <= F2_ZERO_THRESHOLD_USD
        return {"state": "TRIGGERED (KILL)" if all_zero else "CLEAR (untagged payouts)",
                "detail": f"total payout ${total:.2f} (no distance tags on lip_payouts.jsonl rows)"}
    all_zero = all(v <= F2_ZERO_THRESHOLD_USD for v in per_distance_totals.values())
    return {
        "state": "TRIGGERED (KILL)" if all_zero else "CLEAR",
        "per_distance_payout_usd": per_distance_totals,
        "detail": "all ladder distances paid ~$0" if all_zero else "at least one distance paid > $0",
    }


def evaluate_f3(today=None):
    today = today or dt.date.today()
    days_left = (PROGRAM_END_DATE - today).days
    lapsed = days_left <= 0
    return {
        "state": "TRIGGERED (ENDED BY CALENDAR)" if lapsed else "PENDING",
        "program_end_date": PROGRAM_END_DATE.isoformat(),
        "days_to_program_end": days_left,
    }


def evaluate_success_bar(events, payouts, d0):
    """Second-week net (payout - fill P&L - fees) >= $1/day AND projected >= $30/mo. fees are not
    separately logged (Kalshi fee schedule wasn't confirmable offline); treated as $0 here and
    flagged -- a real go/no-go call must pull the fee ledger before trusting this number."""
    if d0 is None:
        return {"state": "PENDING", "detail": "no events yet"}
    week2_start = d0 + dt.timedelta(days=F1_WEEK_DAYS)
    week2_end = d0 + dt.timedelta(days=2 * F1_WEEK_DAYS)
    today = dt.date.today()
    if today < week2_end:
        return {"state": "PENDING", "detail": f"second week ends {week2_end.isoformat()}"}
    pod = payouts_by_date(payouts)
    week2_payout = sum(v for k, v in pod.items() if week2_start.isoformat() <= k < week2_end.isoformat())
    week2_losses = realized_fill_losses_usd(events, since_date=week2_start.isoformat())
    net_per_day = (week2_payout - week2_losses) / F1_WEEK_DAYS
    projected_monthly = net_per_day * 30
    meets_bar = net_per_day >= SUCCESS_BAR_USD_PER_DAY and projected_monthly >= SUCCESS_BAR_USD_PER_MONTH
    return {
        "state": "MEETS BAR (continue)" if meets_bar else "BELOW BAR (publish and stop)",
        "net_usd_per_day": round(net_per_day, 2),
        "projected_usd_per_month": round(projected_monthly, 2),
        "fees_note": "fees not separately tracked in this build -- treated as $0, confirm before a real go/no-go",
    }


def render_report(out=sys.stdout):
    events = load_jsonl(LOG_FILE)
    payouts = load_jsonl(PAYOUTS_FILE)
    cfg = load_markets_cfg()
    d0 = day0(events, cfg)

    m1 = compute_m1(events, payouts)
    m2 = compute_m2(events)
    m3 = compute_m3(events)
    f1 = evaluate_f1(events, payouts, d0)
    f2 = evaluate_f2(m1, payouts)
    f3 = evaluate_f3()
    bar = evaluate_success_bar(events, payouts, d0)

    def p(*a):
        print(*a, file=out)

    p("=" * 78)
    p("LIP_PILOT REPORT -- generated", dt.datetime.now(dt.timezone.utc).isoformat())
    p("=" * 78)
    p(f"day0: {d0.isoformat() if d0 else 'unknown (no events logged yet)'}")
    p(f"program window ends: {PROGRAM_END_DATE.isoformat()}  "
      f"({f3['days_to_program_end']} days remaining)")
    p()
    p("-- M1: $ payout / day / (size x distance x uptime) --")
    p(f"  total payout logged:  ${m1['total_payout_usd']:.4f}")
    p(f"  total ladder uptime:  {m1['total_uptime_days']:.3f} order-days")
    p(f"  aggregate M1:          {m1['m1_aggregate_usd_per_unit']}")
    for row in m1["rows"]:
        p(f"    {row['distance_cents']}c: uptime={row['uptime_days']}d payout=${row['payout_usd']:.4f} "
          f"m1={row['m1_usd_per_unit']}")
    p()
    p("-- M2: fill rate by distance --")
    p(f"  total fills: {m2['n_fills_total']}  total placed: {m2['n_placed_total']}  "
      f"overall rate: {m2['overall_fill_rate']}")
    for row in m2["rows"]:
        p(f"    {row['distance_cents']}c: placed={row['orders_placed']} fill_rate={row['fill_rate']}")
    p()
    p("-- M3: realized per-fill P&L vs -8.81c/ct pessimistic bound --")
    p(f"  fills: {m3['n_fills']}  contracts: {m3['total_fill_contracts']}  "
      f"realized_pnl_cents: {m3['realized_pnl_cents']}")
    p(f"  per-fill c/ct: {m3['per_fill_cents_per_contract']}  "
      f"beats pessimistic bound ({MAKER_VIABILITY_PESSIMISTIC_CPT}c/ct): {m3['beats_pessimistic_bound']}")
    p()
    p("-- Falsifiers --")
    p(f"  F1 (week1 payout < losses+${F1_SLACK_USD}): {f1['state']}  -- {f1.get('detail')}")
    p(f"  F2 (payout ~=$0 at all distances):          {f2['state']}  -- {f2.get('detail')}")
    p(f"  F3 (program lapses {PROGRAM_END_DATE.isoformat()}):        {f3['state']}  "
      f"-- {f3['days_to_program_end']} days left")
    p()
    p("-- Success bar (continue past day 14) --")
    p(f"  {bar['state']}  -- {bar.get('detail', '')}")
    if "net_usd_per_day" in bar:
        p(f"  net/day: ${bar['net_usd_per_day']}  projected/mo: ${bar['projected_usd_per_month']}  "
          f"({bar['fees_note']})")
    p("=" * 78)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="also write the report to this file")
    args = ap.parse_args(argv)
    render_report(sys.stdout)
    if args.out:
        with open(args.out, "w") as fh:
            render_report(fh)


if __name__ == "__main__":
    main()
