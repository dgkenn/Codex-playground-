"""activity_guard.py -- "bot is running but not trading when it definitely should be" guard for
the Kalshi live BTC box maker.

Spec/incident: on 2026-07-13 the bot went 38h with ZERO placements (a sizing-flag bug) while every
existing health check kept saying "running" -- health_check.py watches data-collection freshness,
the live-watchdog step in health.yml watches whether the live.yml WORKFLOW CHAIN is alive, and
pnl_guard.py watches P&L variance. None of those notice "the process is up, telemetry is flowing,
but it has placed zero orders" -- a live process happily emitting `window` records with
placements=0 looks "healthy" to all three. This script is the systematic fix for that blind spot:
it is the ACTIVITY layer, sitting alongside (not replacing) the freshness/chain/P&L guards.

Pre-registered from a 33-day historical analysis of hourly BTC fill-event activity (embedded below
as constants -- an operator decision if these ever need retuning, not something this script tunes
itself, same convention as pnl_guard.py's ESCALATION_PLAN.md thresholds):
  P(zero fill-events in an hour) <= 0.12 for every UTC hour EXCEPT 07 and 08 (~0.21, the
  "lull" -- BTC's quietest hours in the historical sample). P(zero fills in a 2h block) <= 0.06
  outside the lull. That is the statistical basis for firing SEV-AMBER on "0 placements for a
  full trailing 2h during a non-lull hour" -- it's a <6% event if the bot is actually working.

Invoked by health.yml the same way pnl_guard.py is (own step, `|| true` belt-and-suspenders,
`OMP_NUM_THREADS=2` set by the workflow, never fails the job itself). health.yml checks out
$BRANCH (the bot branch) but not `live-state`, so -- exactly like pnl_guard.py -- this script
fetches `live-state` itself and reads it via the git-plumbing pattern established by
sleeve_ledger.py's `_live_state_winrec_rows()` / pnl_guard.py's `load_live_winrec_rows()`: a local
`live_state/` checkout first if one happens to exist, else best-effort `git ls-tree`/`git show`
against a fetched-but-not-checked-out `origin/live-state` ref. Never raises out of that path.

DATA SOURCE: `live_metrics_kalshi_<asset>15m.jsonl` (falling back to the older
`live_metrics_<asset>15m.jsonl` name -- same two-name fallback kalshi_scorecard.py uses), written
by live_metrics.py's `window_summary()` once per settled 15m window as a `kind="window"` record:
`{ws, placements, fills, rejects, cancels, ..., kind:"window", asset, ts}`. `ts` (wall-clock write
time, seconds since epoch) is what this script buckets on -- NOT `ws` (the window-start key) --
because we care about when the bot told us about a window, i.e. genuine telemetry recency.

RULES (checked against `kind="window"` rows in the trailing lookback from "now"):
  0. INTENTIONAL-OFF: LIVE_SWITCH (read off the checked-out bot branch; health.yml already checks
     out $BRANCH before this step, same file the live-watchdog step above it reads) != "on", OR
     the local sticky kill sentinel `.kalshi_killed_<asset>15m` exists (kalshi_trader.py /
     kalshi_preflight.py's own sentinel path/convention) -> exit 0, "intentionally off". No further
     checks matter if the bot was deliberately told to stand down.
  1. DATA-GAP: zero `window` rows at all in the trailing AMBER_WINDOW_HOURS (2h) -> exit 0,
     "telemetry gap" note. This is deliberately NOT an activity alert -- a total telemetry outage
     is health_check.py's (gha-data freshness) and the live-watchdog step's (workflow-chain
     liveness) jurisdiction; this guard staying silent here avoids doubling up on the same root
     cause with a differently-worded alert.
  2. SEV-RED (exit 20): total placements across trailing RED_WINDOW_HOURS (4h) of `window` rows is
     0 -- regardless of hour-of-day (the lull only ever raises P(zero) from ~0.12 to ~0.21 for ONE
     hour; a 4h all-zero span blows through that under any hour-of-day mix).
  3. SEV-AMBER (exit 10): total placements across trailing AMBER_WINDOW_HOURS (2h) of `window` rows
     is 0, AND the current UTC hour is not in the lull ({07, 08}) -- historically a <6% event.
     (If current hour IS in the lull, a 2h-zero span alone is expected often enough not to page;
     it will still escalate to SEV-RED above if it persists into a 4h span.)
  4. OK (exit 0): otherwise -- placements > 0 somewhere in the trailing 2h. One-line confirmation
     with the count.
  Trailing "N full hours" here means a rolling N*3600s lookback ending at "now" (real UTC now, or
  --as-of for tests) -- NOT calendar-hour-aligned buckets. Documented simplification, same spirit
  as pnl_guard.py's non-calendar-strict rolling 3-day sums: at 15-minute window cadence a rolling
  lookback and an hour-bucket lookback agree to within one window either way, and the rolling form
  is what actually answers "how long has it really been since a placement" without edge artifacts
  at the top of the clock hour.

DIAGNOSTIC BREADCRUMBS (spec: "for the debugging loop"): every AMBER/RED/gap message carries
windows_seen / fills / current LIVE_SWITCH / last telemetry age, plus a fixed pointer at the first
place to look: kalshi_trader.py's `[LOOP] ... skips={dict(_skip_ct)}` diagnostic line in the
live.yml run log -- that per-cycle skip-reason breakdown is exactly what would have surfaced the
2026-07-13 sizing-flag bug hours earlier instead of 38h later.

USAGE:
  python3 activity_guard.py                     # real run: fetch+read origin/live-state, now=UTC now
  python3 activity_guard.py --fixture FILE.json  # TEST run: read window rows from FILE.json instead
                                                  # of live-state (never touches git/network)
  python3 activity_guard.py --fixture FILE.json --as-of 2026-07-13T11:00:00Z   # pin "now"
  (env vars ACTIVITY_GUARD_FIXTURE / ACTIVITY_GUARD_AS_OF work the same as the flags, for CI)

  Fixture file schema: {"rows": [ {"ts": <epoch>, "kind": "window", "placements": <int>,
  "fills": <int>, "asset": "btc", ...}, ... ], "live_switch": "on"|"off" (optional, default "on"),
  "kill_sentinel": true|false (optional, default false)}  -- a bare JSON list is also accepted and
  treated as "rows" with live_switch defaulting to "on" and kill_sentinel to false.

Exit codes: 0 OK / intentionally-off / data-gap, 10 SEV-AMBER, 20 SEV-RED. This script's own
failures (bad data, git errors, etc) are caught and reported as OK-exit-0 "guard could not
evaluate" rather than raising -- same convention as pnl_guard.py / health_check.py. health.yml is
still responsible for wrapping the invocation in `|| true` as belt-and-suspenders.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# ------------------------------------------------------------------------------------------------
# PRE-REGISTERED CONSTANTS (33-day historical hourly-activity analysis, 2026-07-13). Do not tune
# without an explicit operator instruction -- same convention as pnl_guard.py's thresholds.
# ------------------------------------------------------------------------------------------------
LIVE_STATE_REMOTE = "origin/live-state"

# Hourly BTC fill-event activity profile (33-day historical). P(zero fill-events in an hour) <=
# 0.12 for every UTC hour except the "lull" hours below (~0.21). P(zero fills in a 2h block) <=
# 0.06 outside the lull -- the statistical basis for SEV-AMBER.
LULL_HOURS_UTC = {7, 8}
LULL_HOUR_P_ZERO = 0.21
NON_LULL_HOUR_P_ZERO = 0.12
NON_LULL_2H_P_ZERO = 0.06

AMBER_WINDOW_HOURS = 2   # SEV-AMBER lookback: trailing 2 full hours, non-lull hour
RED_WINDOW_HOURS = 4     # SEV-RED lookback: trailing 4 full hours, any hour

EXIT_OK, EXIT_AMBER, EXIT_RED = 0, 10, 20

DEBUG_POINTER = ("check '[LOOP] ... skips={}' counters in the live.yml run log "
                  "(first place to look -- per-cycle skip-reason breakdown)")


# ==================================================================================================
# live-state access (git-plumbing pattern mirrored from pnl_guard.py / sleeve_ledger.py's
# `_live_state_winrec_rows()`)
# ==================================================================================================

def _git(*args: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout)


def fetch_live_state() -> None:
    """Best-effort `git fetch origin live-state`. Never raises -- a failed/unavailable fetch just
    falls through to whatever's already reachable (possibly nothing, which degrades to the
    DATA-GAP path, not a crash). Mirrors pnl_guard.py's fetch_live_state()."""
    try:
        _git("fetch", "origin", "live-state", "-q", timeout=60)
    except Exception:
        pass


def _read_jsonl_text(text: str) -> list[dict]:
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def load_live_metrics_rows(asset: str) -> list[dict]:
    """All live_metrics_kalshi_<asset>15m.jsonl rows reachable for `asset` (falling back to the
    older live_metrics_<asset>15m.jsonl name, same fallback kalshi_scorecard.py uses). Local
    live_state/ checkout first, else git-plumbing against a fetched origin/live-state ref (no
    worktree, no checkout of the branch -- matches pnl_guard.py). Returns [] on any failure."""
    fnames = (f"live_metrics_kalshi_{asset}15m.jsonl", f"live_metrics_{asset}15m.jsonl")

    local: list[str] = []
    for fname in fnames:
        local += sorted(glob.glob(f"live_state/*/{fname}")) + sorted(glob.glob(f"live_state/{fname}"))
    if local:
        out = []
        for fp in local:
            try:
                with open(fp) as fh:
                    out.extend(_read_jsonl_text(fh.read()))
            except Exception:
                continue
        return out

    try:
        ls = _git("ls-tree", "-r", "--name-only", LIVE_STATE_REMOTE)
        if ls.returncode != 0:
            return []
        paths = [p for p in ls.stdout.splitlines()
                 if any(p.endswith(f"/{fn}") or p == fn for fn in fnames)]
        out = []
        for p in paths:
            show = _git("show", f"{LIVE_STATE_REMOTE}:{p}")
            if show.returncode != 0:
                continue
            out.extend(_read_jsonl_text(show.stdout))
        return out
    except Exception:
        return []


def read_live_switch(asset: str) -> str:
    """LIVE_SWITCH is a plain checked-in file on the bot branch (one word: on|off), flipped by
    live_switch.sh. health.yml checks out $BRANCH before this step runs (same file its own
    live-watchdog step reads via `tr -d '[:space:]' < LIVE_SWITCH`) so the local file is normally
    already present -- read it directly first. Falls back to git-plumbing against the bot branch
    if this ever runs from a checkout that doesn't have it. Defaults to "on" (fail toward
    EVALUATING, not toward silently swallowing a real inactivity incident) if genuinely
    unreadable -- unlike the live-state fetch, an unreadable LIVE_SWITCH is not expected to be a
    routine/benign condition."""
    try:
        with open("LIVE_SWITCH") as fh:
            v = fh.read().strip().lower()
            if v:
                return v
    except Exception:
        pass
    try:
        head = _git("rev-parse", "--abbrev-ref", "HEAD")
        branch = head.stdout.strip() if head.returncode == 0 else ""
        if branch and branch != "HEAD":
            show = _git("show", f"origin/{branch}:LIVE_SWITCH")
            if show.returncode == 0 and show.stdout.strip():
                return show.stdout.strip().lower()
    except Exception:
        pass
    return "on"


def kill_sentinel_present(asset: str) -> bool:
    """Local sticky kill sentinel (kalshi_trader.py / kalshi_preflight.py convention:
    `.kalshi_killed_<asset>15m`, gitignored, written by the trader process itself on loss-limit
    kill). Best-effort local file check only -- this guard step runs on a fresh health.yml runner,
    a different ephemeral VM from wherever the live bot process itself runs, so this will
    typically read False even during a real kill; the durable signal for that case is
    LIVE_SWITCH=off, which DEADMAN_AUDIT.md fix #1 commits to the branch at kill time (see
    kalshi_trader.py's `_record_kill`) and which `read_live_switch()` above already covers. This
    check is defense-in-depth for the case where this guard ever does run co-located with the
    trader (e.g. a future non-Actions deployment)."""
    try:
        return os.path.exists(f".kalshi_killed_{asset}15m")
    except Exception:
        return False


def load_fixture(path: str) -> tuple[list[dict], str, bool]:
    """Fixture file: {"rows": [...], "live_switch": "on"|"off", "kill_sentinel": bool}, or a bare
    JSON list (treated as "rows" with live_switch="on", kill_sentinel=False)."""
    with open(path) as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data, "on", False
    rows = data.get("rows", [])
    live_switch = str(data.get("live_switch", "on")).strip().lower()
    kill = bool(data.get("kill_sentinel", False))
    return rows, live_switch, kill


# ==================================================================================================
# evaluation
# ==================================================================================================

def _parse_as_of(s: str) -> datetime:
    s = s.strip()
    try:
        return datetime.fromtimestamp(float(s), timezone.utc)
    except Exception:
        pass
    iso = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_ts(row: dict) -> float | None:
    ts = row.get("ts")
    if ts is None:
        return None
    try:
        return float(ts)
    except Exception:
        return None


def _window_rows(rows: list[dict], asset: str) -> list[dict]:
    out = []
    for r in rows:
        if r.get("kind") != "window":
            continue
        if asset and r.get("asset") not in (asset, None):
            continue
        if _row_ts(r) is None:
            continue
        out.append(r)
    return out


def evaluate(all_rows: list[dict], now: datetime, asset: str, live_switch: str,
             kill_sentinel: bool) -> dict:
    now_ts = now.timestamp()
    hour = now.hour

    if live_switch != "on" or kill_sentinel:
        reason = "kill sentinel present" if (kill_sentinel and live_switch == "on") else \
            (f"LIVE_SWITCH={live_switch}" + (", kill sentinel present" if kill_sentinel else ""))
        return {"status": EXIT_OK, "path": "intentional-off", "reason": reason,
                "live_switch": live_switch, "kill_sentinel": kill_sentinel, "hour": hour}

    win = _window_rows(all_rows, asset)
    win.sort(key=_row_ts)

    amber_cut = now_ts - AMBER_WINDOW_HOURS * 3600
    red_cut = now_ts - RED_WINDOW_HOURS * 3600
    win_2h = [r for r in win if amber_cut <= _row_ts(r) <= now_ts]
    win_4h = [r for r in win if red_cut <= _row_ts(r) <= now_ts]

    last_ts = max((_row_ts(r) for r in all_rows if _row_ts(r) is not None), default=None)
    telemetry_age_min = (now_ts - last_ts) / 60.0 if last_ts is not None else None

    if not win_2h:
        return {"status": EXIT_OK, "path": "data-gap", "live_switch": live_switch,
                "kill_sentinel": kill_sentinel, "hour": hour,
                "telemetry_age_min": telemetry_age_min, "windows_seen_4h": len(win_4h)}

    placements_2h = sum(int(r.get("placements") or 0) for r in win_2h)
    fills_2h = sum(int(r.get("fills") or 0) for r in win_2h)
    placements_4h = sum(int(r.get("placements") or 0) for r in win_4h)
    fills_4h = sum(int(r.get("fills") or 0) for r in win_4h)

    base = {
        "live_switch": live_switch, "kill_sentinel": kill_sentinel, "hour": hour,
        "telemetry_age_min": telemetry_age_min,
        "windows_seen_2h": len(win_2h), "windows_seen_4h": len(win_4h),
        "placements_2h": placements_2h, "fills_2h": fills_2h,
        "placements_4h": placements_4h, "fills_4h": fills_4h,
        "in_lull": hour in LULL_HOURS_UTC,
    }

    if placements_4h == 0:
        base["status"] = EXIT_RED
        base["path"] = "red"
        return base

    if placements_2h == 0 and hour not in LULL_HOURS_UTC:
        base["status"] = EXIT_AMBER
        base["path"] = "amber"
        return base

    base["status"] = EXIT_OK
    base["path"] = "ok"
    return base


def format_message(r: dict, asset: str) -> str:
    status = r["status"]
    hour_s = f"{r['hour']:02d}"
    sw = r.get("live_switch", "?")

    if r["path"] == "intentional-off":
        return f"[activity_guard OK] asset={asset} intentionally off ({r['reason']})"

    if r["path"] == "data-gap":
        age = r.get("telemetry_age_min")
        age_s = f"{age:.1f}m" if age is not None else "unknown"
        return (f"[activity_guard OK] asset={asset} telemetry gap - staleness monitor's "
                f"jurisdiction (no window records in trailing {AMBER_WINDOW_HOURS}h; "
                f"last_telemetry_age={age_s} LIVE_SWITCH={sw} hour={hour_s})")

    age = r.get("telemetry_age_min")
    age_s = f"{age:.1f}m" if age is not None else "unknown"
    breadcrumbs = (f"windows_seen_2h={r['windows_seen_2h']} windows_seen_4h={r['windows_seen_4h']} "
                   f"fills_2h={r['fills_2h']} fills_4h={r['fills_4h']} LIVE_SWITCH={sw} "
                   f"last_telemetry_age={age_s} hour={hour_s}")

    if r["path"] == "red":
        return (f"[activity_guard SEV-RED] asset={asset} *** BOT INACTIVE (SEV-RED) *** running "
                f"but 0 placements for {RED_WINDOW_HOURS}h+ (any hour-of-day) -- escalate "
                f"immediately :: {breadcrumbs} :: {DEBUG_POINTER}")

    if r["path"] == "amber":
        return (f"[activity_guard SEV-AMBER] asset={asset} *** BOT INACTIVE *** running but 0 "
                f"placements for {AMBER_WINDOW_HOURS}h during active hours (historical "
                f"P<{NON_LULL_2H_P_ZERO:.0%}) :: {breadcrumbs} :: {DEBUG_POINTER}")

    # ok, placements > 0 in trailing window
    lull_note = " [lull hour, 2h-zero not alarming]" if r.get("in_lull") and r["placements_2h"] == 0 else ""
    return (f"[activity_guard OK] asset={asset} placements={r['placements_2h']} in trailing "
            f"{AMBER_WINDOW_HOURS}h (windows={r['windows_seen_2h']} fills={r['fills_2h']}) -- "
            f"bot active{lull_note} :: {breadcrumbs}")


# ==================================================================================================
# CLI
# ==================================================================================================

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fixture", default=os.environ.get("ACTIVITY_GUARD_FIXTURE"),
                     help="JSON file of window-row fixtures; bypasses live-state entirely (testing only)")
    ap.add_argument("--as-of", default=os.environ.get("ACTIVITY_GUARD_AS_OF"),
                     help="Override 'now' (UTC, ISO8601 or epoch seconds). Defaults to real UTC now.")
    ap.add_argument("--asset", default="btc")
    args = ap.parse_args(argv)

    try:
        now = _parse_as_of(args.as_of) if args.as_of else datetime.now(timezone.utc)

        if args.fixture:
            rows, live_switch, kill = load_fixture(args.fixture)
        else:
            fetch_live_state()
            rows = load_live_metrics_rows(args.asset)
            live_switch = read_live_switch(args.asset)
            kill = kill_sentinel_present(args.asset)

        result = evaluate(rows, now, args.asset, live_switch, kill)
        msg = format_message(result, args.asset)
        print(msg)
        return result["status"]
    except Exception as e:
        print(f"[activity_guard OK] guard could not evaluate this cycle ({type(e).__name__}: {e}) "
              f"-- treating as non-fatal, no alert", file=sys.stderr)
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
