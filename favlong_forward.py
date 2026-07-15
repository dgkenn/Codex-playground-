#!/usr/bin/env python3
"""favlong_forward.py -- FORWARD-VALIDATION HARNESS for the FAVLONG edge (node FAVLONG).

WHAT: judges the near-expiry contrarian-taker edge PROSPECTIVELY, on tick-archive days that
arrive AFTER 2026-07-14 (data the strategy's design never saw). It does NOT re-derive the edge:
it imports favlongshot_edge.build_asset / .score and re-runs them with the ONE validated config
(decision_t=720, edge=0.05, +Kalshi fees, clean market-settlement labels, no fill lag), then
appends one per-(asset,day) result record to favlong_forward_log.jsonl and prints the running
POOLED gate status.

GATE (from FORWARD_LEDGER.md / charter, do not relax): pooled per-(asset,day) day-clustered
t >= 2 over >= 10 FORWARD days (days strictly AFTER 2026-07-14), across btc/eth/sol.
  - PASSED  : >= 10 forward days AND pooled t >= 2
  - FAILED  : >= 10 forward days AND pooled t < 0   (=> kill per charter)
  - not-yet : otherwise (clock not started, too few days, or 0 <= t < 2)

IDEMPOTENT: keyed on (asset, day); days already in the log are skipped. Only COMPLETE forward
days (strictly before today UTC) are scored, so a logged day's data is final and never changes
(same "a completed day never changes" discipline as box-shadow.yml).

Usage:
  python favlong_forward.py            # fetch gha-data, score new complete forward days, print gate
  python favlong_forward.py --report   # just print the gate status from the existing log (no fetch)
"""
import subprocess, json, os, sys, math, time, statistics
from datetime import datetime, timezone

import favlongshot_edge as fav

ASSETS = ["btc", "eth", "sol"]
FORWARD_START = "2026-07-14"     # forward clock = tick-archive days STRICTLY AFTER this
GATE_MIN_DAYS = 10
GATE_T = 2.0
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "favlong_forward_log.jsonl")
# the single validated config; keys match favlongshot_edge.score(...) kwargs
CONFIG = dict(decision_t=fav.DECISION_T, edge=fav.EDGE, fee=True, lag=0)


def _git_fetch_gha_data(retries=5):
    """git fetch origin gha-data with retry/backoff; returns True on success."""
    for i in range(retries):
        r = subprocess.run(["git", "fetch", "--depth=1", "origin", "gha-data"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return True
        sys.stderr.write(f"git fetch gha-data failed (attempt {i+1}/{retries}): "
                         f"{r.stderr.strip()[:200]}\n")
        time.sleep(min(2 ** i, 30))
    return False


def load_log():
    recs = []
    if os.path.exists(LOG):
        with open(LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except Exception:
                    continue
    return recs


def append_records(new_recs):
    with open(LOG, "a") as f:
        for r in new_recs:
            f.write(json.dumps(r) + "\n")


def score_day(data, asset, day):
    """Score one (asset, day) with the validated config. Always returns a record (n_trades=0
    marks a complete forward day that produced no qualifying trades, so it isn't re-scanned)."""
    r = fav.score(data, [day], **CONFIG)
    if not r:
        return dict(asset=asset, day=day, n_trades=0, mean_ct=None, day_pnl=0.0,
                    winrate=None, config=CONFIG)
    return dict(asset=asset, day=day, n_trades=r["n"], mean_ct=r["mean"], day_pnl=r["total"],
                winrate=r["winrate"], config=CONFIG)


def compute_gate(recs):
    """Pooled per-(asset,day) day-clustered t over traded forward records."""
    traded = [r for r in recs if r.get("n_trades", 0) > 0 and r.get("mean_ct") is not None]
    means = [r["mean_ct"] for r in traded]
    days = sorted({r["day"] for r in traded})
    ndays = len(days)
    n_points = len(means)
    total_pnl = sum(r.get("day_pnl", 0.0) or 0.0 for r in traded)
    t = float("nan")
    mean_ct = float("nan")
    if n_points >= 1:
        mean_ct = statistics.mean(means)
    if n_points > 1 and statistics.stdev(means) > 0:
        t = statistics.mean(means) / (statistics.stdev(means) / math.sqrt(n_points))

    if ndays == 0:
        status = "CLOCK-NOT-STARTED"
    elif ndays < GATE_MIN_DAYS:
        status = "not-yet"
    elif not math.isnan(t) and t >= GATE_T:
        status = "PASSED"
    elif not math.isnan(t) and t < 0:
        status = "FAILED"
    else:
        status = "not-yet"
    return dict(status=status, ndays=ndays, n_points=n_points, t=t, mean_ct=mean_ct,
                total_pnl=total_pnl, days=days, n_pos=sum(1 for m in means if m > 0))


def print_gate(recs):
    g = compute_gate(recs)
    print("\n=== FAVLONG forward gate ===")
    print(f"config: decision_t={CONFIG['decision_t']}s edge={CONFIG['edge']} "
          f"fees={CONFIG['fee']} lag={CONFIG['lag']}  (POOLED btc+eth+sol)")
    if g["ndays"] == 0:
        print("forward clock has NOT started: no COMPLETE forward day (> "
              f"{FORWARD_START}) with trades is logged yet.")
        print(f"status: {g['status']}  (gate opens after >= {GATE_MIN_DAYS} forward days, "
              f"pooled t >= {GATE_T})")
        return g
    tstr = "nan" if math.isnan(g["t"]) else f"{g['t']:+.2f}"
    print(f"forward days: {g['ndays']} (gate needs >= {GATE_MIN_DAYS})   "
          f"per-(asset,day) points: {g['n_points']} ({g['n_pos']} positive)")
    print(f"pooled mean: ${g['mean_ct']:+.4f}/ct   pooled day-clustered t: {tstr}   "
          f"forward total P&L: ${g['total_pnl']:+.2f}")
    print(f"days: {', '.join(g['days'])}")
    verdict = {
        "PASSED": f"PASSED -- >= {GATE_MIN_DAYS} forward days and pooled t >= {GATE_T}.",
        "FAILED": f"FAILED -- >= {GATE_MIN_DAYS} forward days and pooled t < 0 => KILL per charter.",
        "not-yet": (f"not-yet -- "
                    + ("need more forward days." if g["ndays"] < GATE_MIN_DAYS
                       else f"have >= {GATE_MIN_DAYS} days but pooled t < {GATE_T} (not < 0).")),
    }[g["status"]]
    print(f"status: {verdict}")
    return g


def run(fetch=True):
    if fetch:
        if not _git_fetch_gha_data():
            sys.stderr.write("WARN: could not fetch origin gha-data; scoring against local refs.\n")
    recs = load_log()
    keys = {(r["asset"], r["day"]) for r in recs}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new = []
    for asset in ASSETS:
        try:
            data = fav.build_asset(asset)   # fresh reconstruction (no stale pkl cache)
        except Exception as e:
            sys.stderr.write(f"build_asset({asset}) failed: {e}\n")
            continue
        # COMPLETE forward days only: strictly after the forward start AND strictly before today UTC
        days = [d for d in sorted(data) if FORWARD_START < d < today]
        for day in days:
            if (asset, day) in keys:
                continue
            rec = score_day(data, asset, day)
            new.append(rec)
            keys.add((asset, day))
            nt = rec["n_trades"]
            mc = rec["mean_ct"]
            mcs = "n/a" if mc is None else f"${mc:+.4f}/ct"
            print(f"scored {asset} {day}: n_trades={nt} mean={mcs} day_pnl=${rec['day_pnl']:+.2f}")
    if new:
        append_records(new)
        recs += new
        print(f"appended {len(new)} new record(s) to {LOG}")
    else:
        print("no new complete forward days to score (clock may not have started, or all logged).")
    print_gate(recs)


def main():
    if "--report" in sys.argv[1:]:
        recs = load_log()
        if not recs:
            print(f"no log yet at {LOG} -- forward clock has not started.")
        print_gate(recs)
        return
    run(fetch=True)


if __name__ == "__main__":
    main()
