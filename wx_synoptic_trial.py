#!/usr/bin/env python3
"""wx_synoptic_trial.py -- side-by-side DETECTION-LATENCY measurement: Synoptic 1-min vs the free feeds.

WHY: the single biggest modeled EV lever is the paid Synoptic HF-ASOS feed (~$900 -> ~$2,280/mo modeled,
kwx_runner._synoptic_primary / kwx_bankroll_curve) -- but the decision to PAY must be evidence-based. This
tool runs during the free 14-day trial and measures the thing the money actually buys: how many minutes
EARLIER Synoptic shows each new running-max (the lock precursor) than the free MADIS/weather.gov path.
The gap half-life is ~3.3 min (KWX_DEPLOY.md), so minutes of detection lead ARE the edge.

METHOD (no reimplemented feeds -- reuses the runner's own classes): each poll cycle asks BOTH paths for the
LST-day running extreme per station: (a) synoptic_feed.SynopticFeed (1-min HF-ASOS, token-gated) and
(b) kwx_runner's FREE cascade (madis_feed.MadisFeed 5-min primary -> weather.gov/METAR consensus fallback)
-- exactly the feeds the live bot would use. When a feed CROSSES to a new running-max value in-run, that
crossing is timestamped; when the other feed later crosses the same value, the pair is a LAG SAMPLE:
lag_min = free_first_seen - synoptic_first_seen. Only in-run crossings count (a value either feed already
carried at its first poll is baseline, not a detection), so every sample is a genuine detection race.

Degrades cleanly with NO token: measures the free feeds only and says so -- the GitHub cron can start
accruing free-baseline evidence before the trial is even signed up for.

Appends structured jsonl (wx_synoptic_trial.jsonl); `--report` turns accrued lag samples into the decision
evidence: median/p90 detection-lead in minutes + the implied captured-EV difference per contract from the
published decay curve (see EV_CURVE below for the exact citations).

Usage:
  python wx_synoptic_trial.py --minutes 12                 # one bounded measurement run (cron-sized)
  python wx_synoptic_trial.py --minutes 3 --interval 30    # quick live sanity run
  python wx_synoptic_trial.py --report                     # decision evidence from accrued jsonl
READ-ONLY: obs feeds only, no Kalshi, no orders, no creds. stdlib + the repo's own feed modules.
"""
import argparse, json, os, sys, time, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kwx_runner as R            # reuse: CITY station/offset map + the FREE feed cascade (do not reimplement)
import synoptic_feed              # reuse: SynopticFeed + have_token()

LOG_PATH = os.path.join(HERE, "wx_synoptic_trial.jsonl")
NO_TOKEN_MSG = "no Synoptic token -- free-feed baseline only"

# Default stations: a spread of fire-active cities (KDEN is hourly-on-free -> shows the worst free-feed
# case; the others have MADIS 5-min). Any station in kwx_runner.CITY works via --stations.
DEFAULT_STATIONS = ["KDEN", "KMIA", "KLAS", "KPHX", "KDFW", "KATL"]
STATION_OFFSET = {station: off for _, (station, off) in R.CITY.items()}

# Captured-EV decay curve (PUBLISHED, cited -- do not re-derive here):
#   KWX_DEPLOY.md "The speed problem": gap half-life ~3.3 min; captured EV +0.187/ct if we act at the
#   cross, +0.15-0.17/ct at 2-5 min, ~nothing by 60 min.
#   DECISION_MAP.md "PHASE-2 SYNTHESIS (2026-07-18)" NET REALISTIC EV: +0.15-0.17/ct at Synoptic's
#   ~2-5 min band vs +0.207 at act@0; free feeds (16-24 min) -> gap mostly gone.
# Anchor points below are that curve, linearly interpolated between anchors, clamped outside.
EV_CURVE = [(0.0, 0.187), (2.0, 0.17), (5.0, 0.15), (60.0, 0.0)]
SYN_ACT_MIN = 2.0   # assume we act at the fast band's floor (Synoptic ~2-5 min, DECISION_MAP TIER-2 item 5)


def ev_at(minutes):
    """Captured EV per contract if we act `minutes` after the cross (piecewise-linear on EV_CURVE)."""
    m = max(0.0, float(minutes))
    if m >= EV_CURVE[-1][0]:
        return EV_CURVE[-1][1]
    for (x0, y0), (x1, y1) in zip(EV_CURVE, EV_CURVE[1:]):
        if m <= x1:
            return y0 + (y1 - y0) * (m - x0) / (x1 - x0)
    return EV_CURVE[-1][1]


def _now():
    return dt.datetime.now(tz=dt.timezone.utc)


def _append(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def _poll(feed, station, lst_date, offset, kind):
    """One feed poll -> (running_extreme_value_rounded, newest_obs_iso) or (None, None). Never raises --
    a feed error this cycle just contributes nothing (the race continues next cycle)."""
    try:
        r = feed.running_extreme(station, lst_date, offset, kind)
    except Exception:
        return None, None
    if not r or r.get("extreme_f") is None:
        return None, None
    obs = r.get("obs") or []
    newest = obs[-1][0] if obs else None
    # round to 0.1F: the feeds carry different native precisions (Synoptic F vs MADIS Kelvin->F vs METAR
    # tenths-C->F); the race is over RUNNING-MAX THRESHOLDS, and >= comparison absorbs sub-0.1 jitter.
    return round(float(r["extreme_f"]), 1), newest


def _crossed(kind, prev, val, v):
    """Did a feed moving prev->val cross threshold v this cycle? (upward for max, downward for min)."""
    return (prev < v <= val) if kind == "max" else (val <= v < prev)


def run(stations, minutes, interval_s, kind, out_path):
    feeds = {}
    if synoptic_feed.have_token():
        feeds["synoptic"] = synoptic_feed.SynopticFeed()
    else:
        print(NO_TOKEN_MSG)
    feeds["free"] = R._FREE           # the runner's own free cascade: MADIS 5-min -> wgov/METAR consensus

    stations = [s for s in stations if s in STATION_OFFSET]
    start = _now()
    _append(out_path, {"type": "run_start", "ts": start.isoformat(), "stations": stations,
                       "minutes": minutes, "interval_s": interval_s, "kind": kind,
                       "synoptic": "synoptic" in feeds, "feeds": sorted(feeds)})
    print(f"trial run: {len(stations)} stations x {minutes} min @ {interval_s}s, kind={kind}, "
          f"feeds={sorted(feeds)}")

    # per-station race state: last value per feed + threshold registry {value: {feed: first_seen_iso}}
    last = {st: {} for st in stations}          # station -> {feed: last_value}
    thresholds = {st: {} for st in stations}    # station -> {value: {feed: iso_ts}}
    n_lag = 0
    deadline = start + dt.timedelta(minutes=minutes)
    while True:
        cyc_t = _now()
        for st in stations:
            off = STATION_OFFSET[st]
            lst_date = (cyc_t + dt.timedelta(hours=off)).date().isoformat()
            for fname, feed in feeds.items():
                val, newest = _poll(feed, st, lst_date, off, kind)
                if val is None:
                    continue
                prev = last[st].get(fname)
                last[st][fname] = val
                if prev is None or (val <= prev if kind == "max" else val >= prev):
                    continue          # first poll (baseline, not a detection) or no new extreme
                ts = _now().isoformat()
                _append(out_path, {"type": "obs_event", "ts": ts, "station": st, "kind": kind,
                                   "feed": fname, "value": val, "prev": prev})
                print(f"  {ts} {st} {fname}: new running-{kind} {prev} -> {val}")
                # this feed's crossing stamps every threshold it just passed, incl. its own new value
                reg = thresholds[st]
                reg.setdefault(val, {})
                for v, seen in reg.items():
                    if fname not in seen and _crossed(kind, prev, val, v):
                        seen[fname] = ts
                        if "synoptic" in seen and "free" in seen:
                            lag = ((dt.datetime.fromisoformat(seen["free"])
                                    - dt.datetime.fromisoformat(seen["synoptic"])).total_seconds() / 60.0)
                            n_lag += 1
                            _append(out_path, {"type": "lag_sample", "ts": ts, "station": st,
                                               "kind": kind, "value": v, "syn_ts": seen["synoptic"],
                                               "free_ts": seen["free"], "lag_min": round(lag, 2)})
                            print(f"    LAG SAMPLE {st} @{v}F: free trails synoptic by {lag:+.1f} min")
        if _now() >= deadline:
            break
        time.sleep(max(1.0, min(interval_s, (deadline - _now()).total_seconds())))

    # end-of-run snapshot: per station/feed running extreme + obs freshness (feed-health evidence)
    end = _now()
    for st in stations:
        off = STATION_OFFSET[st]
        lst_date = (end + dt.timedelta(hours=off)).date().isoformat()
        for fname, feed in feeds.items():
            val, newest = _poll(feed, st, lst_date, off, kind)
            age = None
            if newest:
                try:
                    age = round((end - dt.datetime.fromisoformat(
                        str(newest).replace("Z", "+00:00"))).total_seconds() / 60.0, 1)
                except ValueError:
                    pass
            _append(out_path, {"type": "snapshot", "ts": end.isoformat(), "station": st, "kind": kind,
                               "feed": fname, "value": val, "newest_obs_ts": newest, "age_min": age})
    _append(out_path, {"type": "run_end", "ts": end.isoformat(), "n_lag_samples": n_lag,
                       "synoptic": "synoptic" in feeds})
    print(f"run done: {n_lag} new lag samples -> {out_path}"
          + ("" if "synoptic" in feeds else f" ({NO_TOKEN_MSG})"))


def report(out_path):
    """Turn accrued lag samples into the pay/don't-pay decision evidence."""
    if not os.path.exists(out_path):
        print(f"no log at {out_path} -- run some measurement cycles first")
        return
    lags, events, syn_runs = [], {"synoptic": 0, "free": 0}, 0
    with open(out_path) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") == "lag_sample":
                lags.append(rec["lag_min"])
            elif rec.get("type") == "obs_event":
                events[rec.get("feed", "?")] = events.get(rec.get("feed", "?"), 0) + 1
            elif rec.get("type") == "run_start" and rec.get("synoptic"):
                syn_runs += 1
    print("== Synoptic trial: detection-latency evidence ==")
    print(f"obs events: synoptic={events.get('synoptic', 0)} free={events.get('free', 0)}; "
          f"runs with Synoptic token: {syn_runs}")
    if not lags:
        print("no paired lag samples yet -- " +
              ("keep the cron accruing during afternoon fire windows" if syn_runs
               else NO_TOKEN_MSG + " (sign up for the trial + set SYNOPTIC_TOKEN to start the race)"))
        return
    ls = sorted(lags)
    med = ls[len(ls) // 2]
    p90 = ls[min(len(ls) - 1, int(round(0.9 * (len(ls) - 1))))]
    print(f"lag samples n={len(ls)}: free trails Synoptic by median {med:+.1f} min, p90 {p90:+.1f} min")
    # implied captured-EV per contract, from the PUBLISHED decay curve (KWX_DEPLOY.md 'The speed problem';
    # DECISION_MAP.md PHASE-2 SYNTHESIS): acting at Synoptic detection ~= act@2 min (its own feed latency
    # floor), acting at free detection = 2 min + measured lag.
    ev_syn = ev_at(SYN_ACT_MIN)
    for label, lag in (("median", med), ("p90", p90)):
        ev_free = ev_at(SYN_ACT_MIN + max(0.0, lag))
        print(f"  implied captured EV ({label} lag): synoptic {ev_syn:+.3f}/ct vs free {ev_free:+.3f}/ct"
              f" -> advantage {ev_syn - ev_free:+.3f}/ct")
    print("curve: +0.187/ct at the cross, +0.15-0.17/ct at 2-5 min, ~0 by 60 min (gap half-life 3.3 min)"
          "\n  [KWX_DEPLOY.md 'The speed problem'; DECISION_MAP.md 'PHASE-2 SYNTHESIS' NET REALISTIC EV]"
          "\ndecision: pay for Synoptic iff this measured advantage x fire throughput clears the feed cost"
          " (~$900 -> ~$2,280/mo modeled, kwx_bankroll_curve via kwx_runner._synoptic_primary).")


def main():
    ap = argparse.ArgumentParser(description="Synoptic-vs-free detection-latency trial harness")
    ap.add_argument("--minutes", type=float, default=12.0, help="bounded run length (default 12, cron-sized)")
    ap.add_argument("--interval", type=float, default=60.0, help="poll interval seconds (default 60)")
    ap.add_argument("--stations", default=",".join(DEFAULT_STATIONS),
                    help="comma-separated station ids from kwx_runner.CITY")
    ap.add_argument("--kind", choices=["max", "min"], default="max",
                    help="running extreme to race (afternoon crons -> max)")
    ap.add_argument("--out", default=LOG_PATH, help="jsonl path (append)")
    ap.add_argument("--report", action="store_true", help="summarize accrued evidence instead of running")
    a = ap.parse_args()
    if a.report:
        report(a.out)
    else:
        run([s.strip() for s in a.stations.split(",") if s.strip()], a.minutes, a.interval, a.kind, a.out)


if __name__ == "__main__":
    main()
