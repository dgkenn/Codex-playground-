"""pnl_guard.py -- statistical P&L variance guard for the Kalshi 15m BTC box maker.

Spec: ESCALATION_PLAN.md, section "MONITORING" (pre-registered 2026-07-13). This is the
STATISTICAL companion to the plan's fixed dollar loss-limits -- it catches "losing more than
the strategy's own distribution says is plausible", not just catastrophic dollar losses.
Thresholds below are pre-registered in that file; changing them is an operator decision, not
something this script should ever do on its own.

Invoked by health.yml every 30 min (same cadence as the rest of the health monitor). health.yml
checks out $BRANCH (the bot branch) but NOT the live-state branch (confirmed by reading
.github/workflows/health.yml on main: its only `git fetch origin <branch>` is for `gha-data`,
used by health_check.py -- there is no existing live-state read to mirror there). So this script
is self-sufficient the same way health_check.py is self-sufficient for gha-data: it fetches
`live-state` itself, then reads it via the git-plumbing pattern already established in this repo
by sleeve_ledger.py's `_live_state_winrec_rows()` (itself documented as mirroring live_gate.py):
a local `live_state/` checkout first if one happens to exist, else best-effort
`git ls-tree`/`git show` straight out of a fetched-but-not-checked-out `origin/live-state` ref.
Never raises out of that path -- a missing/unfetchable branch degrades to "no live data yet",
which just pushes this script further into the prior-seeded regime below, not to a crash.

METRICS computed (ESCALATION_PLAN.md MONITORING):
  - today's realized P&L            sum of `realized` over today's UTC-day winrec rows
  - 3-day cumulative P&L            today + previous 2 UTC calendar days
  - consecutive negative days       trailing streak of traded days with P&L < 0 (today included,
                                     using its P&L-so-far -- this is a live monitor, not an EOD one)
  - 3-day strand rate               stranded windows / traded windows, trailing 3 UTC calendar days

EXPECTED DISTRIBUTION (ESCALATION_PLAN.md verbatim):
  "rolling 30-day empirical distribution of daily live P&L (from live-state winrec; while live
  history is thin, seeded with the replay distribution scaled to current size, clearly labeled
  as prior)."

  Concretely, in this implementation:
    * >= MIN_LIVE_DAYS_FOR_EMPIRICAL (10) traded live days on record: EMPIRICAL. Percentiles come
      straight off up to the trailing ROLLING_WINDOW_DAYS (30) traded days' realized daily P&L via
      np.percentile. No prior term at all once there's enough data to ask numpy for a 5th/1st
      percentile without kidding ourselves.
    * < 10 traded live days (including zero): PRIOR-SEEDED BLEND. Below 10 samples an empirical
      5th/1st percentile is close to meaningless (a "5th percentile of 3 numbers" is just
      "roughly the smallest one"), so the expected distribution is instead modeled as a Normal
      whose mean/sd is a weight-blend (weight w = n_live_days / 10) of:
        (a) the REPLAY PRIOR -- LABELED, NOT DATA. See PRIOR_MEAN_PER_WINDOW_USD /
            PRIOR_SD_PER_WINDOW_USD below: -0.5c and 8c per traded window respectively, scaled to
            whatever window-count is in play (a day's own traded-window count, or the summed
            traded-window count across a 3-day span) under an independence-across-windows
            assumption (mu scales linearly with n, sd scales with sqrt(n)); and
        (b) the empirical mean/variance of whatever live days DO exist (0 live days -> pure prior,
            w=0).
      Percentiles of that blended Normal are read off the fixed standard-normal quantiles
      (Z_05, Z_01 below) via mu + Z*sigma -- no scipy dependency (this script is stdlib+numpy
      only; the collector env also carries scipy/requests/websockets but this script doesn't need
      them).
    Any time the day-level expected distribution used this blended path, the printed message
    contains the literal substring "prior-seeded" so operators (and this repo's fixture tests)
    can tell at a glance which regime produced a given alert.

SEVERITY (ESCALATION_PLAN.md MONITORING, verbatim thresholds):
  SEV-AMBER (exit 10): today's P&L below the expected day distribution's 5th percentile, OR the
    3-day cumulative below the expected 3-day distribution's 5th percentile. Alert with the
    numbers; no automatic action (daily cycle must acknowledge it in the scoreboard -- that's a
    human/process step, out of scope for this script).
  SEV-RED (exit 20): today's P&L below the expected day distribution's 1st percentile, OR 5
    consecutive negative [traded] days when the expected P(5 straight negative days) < 5%, OR the
    realized 3-day strand rate > 2x the expected strand rate. Alert; the de-escalation rule and
    escalation-clock freeze in ESCALATION_PLAN.md's "De-escalation" section are OPERATOR actions
    this script only reports the trigger for -- it does not touch LIVE_SWITCH, bankroll, or the
    ladder step itself.
  OK (exit 0): none of the above. One-line confirmation.

RED is a strict superset check over AMBER (if both would fire, RED wins and is reported; AMBER
conditions are still included in the message for context).

USAGE:
  python3 pnl_guard.py                        # real run: fetch+read origin/live-state, today=UTC now
  python3 pnl_guard.py --fixture FILE.json     # TEST run: read winrec rows from FILE.json instead
                                                # of live-state (never touches git/network)
  python3 pnl_guard.py --fixture FILE.json --as-of 2026-07-01   # pin "today" for reproducibility
  (env vars PNL_GUARD_FIXTURE / PNL_GUARD_AS_OF work the same as the flags, for CI convenience)

Exit codes: 0 OK, 10 SEV-AMBER, 20 SEV-RED. This script's own failures (bad data, git errors, etc)
are caught and reported as OK-exit-0 "guard could not evaluate" rather than raising, matching the
"guard failures of the script itself must not fail the workflow" convention used elsewhere in this
repo (health_check.py's `exit 0 # never fail the monitor itself` is the model) -- health.yml is
still responsible for wrapping the invocation itself in `|| true` as belt-and-suspenders.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

# ------------------------------------------------------------------------------------------------
# PRE-REGISTERED CONSTANTS (ESCALATION_PLAN.md MONITORING). Do not tune these without an explicit
# operator instruction landing in ESCALATION_PLAN.md first -- that's the whole point of the plan.
# ------------------------------------------------------------------------------------------------
LIVE_STATE_REMOTE = "origin/live-state"

# LABELED REPLAY PRIOR -- NOT DATA. Seed values for the expected P&L distribution while live
# history is thin (ESCALATION_PLAN.md: "seeded with the replay distribution scaled to current
# size, clearly labeled as prior"). -0.5c/window mean, 8c/window sd, per-traded-window.
PRIOR_MEAN_PER_WINDOW_USD = -0.005
PRIOR_SD_PER_WINDOW_USD = 0.08

# LABELED PRIOR for the expected strand rate while live history is thin. Sourced from
# ESCALATION_PLAN.md's own ladder step-2 gate language ("strand rate < 4.3% break-even"), which
# in turn traces to box_regime.py's STRAND_BE = 0.044 (post-fix break-even strand rate). Used
# only until >= MIN_LIVE_DAYS_FOR_EMPIRICAL live days exist, same as the P&L prior.
EXPECTED_STRAND_RATE_PRIOR = 0.043

MIN_LIVE_DAYS_FOR_EMPIRICAL = 10   # below this: prior-seeded blend. At/above: rolling empirical.
ROLLING_WINDOW_DAYS = 30           # "rolling 30-day empirical distribution"

CONSEC_NEG_DAYS_RED = 5            # SEV-RED: 5 consecutive negative days ...
CONSEC_NEG_DAYS_P_MAX = 0.05       # ... when expected P(5 straight negatives) < 5%
STRAND_RED_MULTIPLE = 2.0          # SEV-RED: realized strand rate > 2x expected over 3 days
MIN_TRADED_FOR_STRAND_CHECK = 5    # don't fire the strand check off a handful of windows (noise)

# Fixed standard-normal quantiles (avoids a scipy.stats.norm.ppf dependency -- stdlib+numpy only).
Z_05 = -1.6448536269514722   # Phi^-1(0.05)
Z_01 = -2.3263478740408408   # Phi^-1(0.01)

EXIT_OK, EXIT_AMBER, EXIT_RED = 0, 10, 20


# ==================================================================================================
# live-state access (git-plumbing pattern mirrored from sleeve_ledger.py's
# `_live_state_winrec_rows()`, which itself documents mirroring live_gate.py's pattern)
# ==================================================================================================

def _git(*args: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout)


def fetch_live_state() -> None:
    """Best-effort `git fetch origin live-state`. Never raises -- a failed/unavailable fetch just
    means we fall through to whatever's already reachable (possibly nothing, which degrades to
    the pure-prior regime, not a crash). Mirrors health_check.py's `fetch()` / health.yml's
    `git fetch origin gha-data -q || true` convention for the sibling data branch."""
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


def load_live_winrec_rows(asset: str) -> list[dict]:
    """All kalshi_winrec_<asset>15m.jsonl rows reachable for `asset`. Local live_state/ checkout
    first (if this ever runs somewhere that has one), else git-plumbing against a fetched
    origin/live-state ref (no worktree, no checkout of the branch -- matches sleeve_ledger.py).
    Returns [] on any failure; never raises."""
    fname = f"kalshi_winrec_{asset}15m.jsonl"
    local = sorted(glob.glob(f"live_state/*/{fname}")) + sorted(glob.glob(f"live_state/{fname}"))
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
        paths = [p for p in ls.stdout.splitlines() if p.endswith(f"/{fname}") or p == fname]
        out = []
        for p in paths:
            show = _git("show", f"{LIVE_STATE_REMOTE}:{p}")
            if show.returncode != 0:
                continue
            out.extend(_read_jsonl_text(show.stdout))
        return out
    except Exception:
        return []


def load_fixture_rows(path: str) -> list[dict]:
    """Fixture rows for testing: a JSON file holding a list of winrec-row dicts (same schema as a
    real kalshi_winrec_btc15m.jsonl line: ws, realized, n_boxes/n_yes/n_no, stranded, asset)."""
    with open(path) as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("rows", [])
    return list(data)


# ==================================================================================================
# aggregation
# ==================================================================================================

def _utc_day(row: dict) -> str | None:
    ts = row.get("ws")
    if ts is None:
        ts = row.get("ts")
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


def _is_traded(row: dict) -> bool:
    """A window counts as 'traded' (vs merely quoted-but-unfilled) when a box actually formed.
    n_boxes is the direct signal; fall back to n_yes+n_no for older rows that might lack it."""
    nb = row.get("n_boxes")
    if nb is not None:
        try:
            return float(nb) > 0
        except Exception:
            pass
    return (float(row.get("n_yes") or 0) + float(row.get("n_no") or 0)) > 0


class DayStats:
    __slots__ = ("pnl", "n_traded", "n_stranded")

    def __init__(self) -> None:
        self.pnl = 0.0
        self.n_traded = 0
        self.n_stranded = 0

    def __repr__(self) -> str:
        return f"DayStats(pnl={self.pnl!r}, n_traded={self.n_traded!r}, n_stranded={self.n_stranded!r})"


def bucket_by_day(rows: list[dict], asset: str) -> dict[str, DayStats]:
    out: dict[str, DayStats] = defaultdict(DayStats)
    for r in rows:
        if asset and r.get("asset") not in (asset, None):
            continue
        day = _utc_day(r)
        if day is None:
            continue
        st = out[day]
        traded = _is_traded(r)
        if traded:
            st.n_traded += 1
            st.pnl += float(r.get("realized") or 0.0)
            if r.get("stranded"):
                st.n_stranded += 1
    return dict(out)


# ==================================================================================================
# expected-distribution model
# ==================================================================================================

class ExpectedDist:
    """Either an empirical sample (mode='empirical') or a blended-Normal (mode='prior-seeded')."""

    def __init__(self, mode: str, mu: float, sigma: float, sample: np.ndarray | None):
        self.mode = mode
        self.mu = mu
        self.sigma = max(sigma, 1e-6)   # epsilon floor: avoids /0 in the p_neg calc below when a
        self.sample = sample            # brand-new bot has traded zero windows so far (sigma==0)

    def pct(self, p: float) -> float:
        if self.mode == "empirical" and self.sample is not None and len(self.sample):
            return float(np.percentile(self.sample, p))
        z = {5: Z_05, 1: Z_01}[p]
        return self.mu + z * self.sigma

    def p_negative(self) -> float:
        """P(day P&L < 0) under this expected distribution."""
        if self.mode == "empirical" and self.sample is not None and len(self.sample):
            return float(np.mean(self.sample < 0))
        z = (0.0 - self.mu) / self.sigma
        return 0.5 * (1.0 + math.erf(-z / math.sqrt(2.0)))   # Phi(-z) == P(X<0) for X~N(mu,sigma)


def _blend_normal(history: list[float], n_live: int, prior_mu: float, prior_sigma: float) -> tuple[float, float]:
    w = min(n_live, MIN_LIVE_DAYS_FOR_EMPIRICAL) / MIN_LIVE_DAYS_FOR_EMPIRICAL
    if n_live > 0:
        live_mu = float(np.mean(history))
        live_var = float(np.var(history, ddof=0)) if n_live > 1 else prior_sigma ** 2
    else:
        live_mu, live_var = 0.0, prior_sigma ** 2
    mu = w * live_mu + (1 - w) * prior_mu
    var = w * live_var + (1 - w) * (prior_sigma ** 2)
    return mu, math.sqrt(max(var, 0.0))


def expected_day_dist(history_pnls: list[float], n_traded_today: int) -> ExpectedDist:
    n_live = len(history_pnls)
    prior_mu = PRIOR_MEAN_PER_WINDOW_USD * n_traded_today
    prior_sigma = PRIOR_SD_PER_WINDOW_USD * math.sqrt(max(n_traded_today, 0))
    if n_live >= MIN_LIVE_DAYS_FOR_EMPIRICAL:
        sample = np.array(history_pnls[-ROLLING_WINDOW_DAYS:], dtype=float)
        return ExpectedDist("empirical", float(np.mean(sample)), float(np.std(sample, ddof=0)) or 1e-6, sample)
    mu, sigma = _blend_normal(history_pnls, n_live, prior_mu, prior_sigma)
    return ExpectedDist("prior-seeded", mu, sigma, None)


def expected_3day_dist(history_pnls: list[float], n_traded_3d: int) -> ExpectedDist:
    """Same regime split as expected_day_dist, but for the trailing 3-CALENDAR-day cumulative.
    Empirical mode uses INDEX-based rolling 3-entry sums over the ordered traded-day history
    (not calendar-contiguous -- early on, traded days are sparse by design, so a calendar-strict
    rolling sum would rarely have 3 eligible days at all; documented simplification)."""
    n_live = len(history_pnls)
    prior_mu = PRIOR_MEAN_PER_WINDOW_USD * n_traded_3d
    prior_sigma = PRIOR_SD_PER_WINDOW_USD * math.sqrt(max(n_traded_3d, 0))
    if n_live >= MIN_LIVE_DAYS_FOR_EMPIRICAL:
        window = history_pnls[-ROLLING_WINDOW_DAYS:]
        sums = [sum(window[i:i + 3]) for i in range(max(len(window) - 2, 0))]
        if sums:
            sample = np.array(sums, dtype=float)
            return ExpectedDist("empirical", float(np.mean(sample)), float(np.std(sample, ddof=0)) or 1e-6, sample)
    # fall back to the prior-seeded 3-day blend (also used when empirical had <1 rolling sum)
    sums_history = [sum(history_pnls[max(0, i - 2):i + 1]) for i in range(len(history_pnls))] if history_pnls else []
    mu, sigma = _blend_normal(sums_history, len(sums_history), prior_mu, prior_sigma)
    return ExpectedDist("prior-seeded", mu, sigma, None)


# ==================================================================================================
# guard evaluation
# ==================================================================================================

def evaluate(days: dict[str, DayStats], today: str, asset: str) -> dict:
    def d(day: str) -> DayStats:
        return days.get(day, DayStats())

    today_dt = datetime.strptime(today, "%Y-%m-%d")
    day_m1 = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    day_m2 = (today_dt - timedelta(days=2)).strftime("%Y-%m-%d")

    st_today, st_m1, st_m2 = d(today), d(day_m1), d(day_m2)

    # -- history for the expected-distribution model: traded days strictly before "today",
    #    chronologically ordered, trailing ROLLING_WINDOW_DAYS at most kept downstream.
    history_days = sorted(day for day, st in days.items() if day < today and st.n_traded > 0)
    history_pnls = [days[day].pnl for day in history_days]
    n_live_days = len(history_pnls)

    # -- observed metrics (real, calendar-based)
    today_pnl = st_today.pnl
    pnl_3d = st_today.pnl + st_m1.pnl + st_m2.pnl
    n_traded_3d = st_today.n_traded + st_m1.n_traded + st_m2.n_traded
    n_stranded_3d = st_today.n_stranded + st_m1.n_stranded + st_m2.n_stranded
    strand_rate_3d = (n_stranded_3d / n_traded_3d) if n_traded_3d > 0 else 0.0

    # -- consecutive negative TRADED days, today included (using P&L-so-far -- this is a live,
    #    intraday monitor, not an end-of-day one). Walk backward from today.
    seq_days = history_days + [today]
    seq_pnls = history_pnls + [today_pnl]
    # only evaluate today in the streak if it has traded at all this cycle (0 traded -> pnl 0.0,
    # which is not negative anyway, so this is mostly a no-op guard against a misleading "0 < ..").
    streak = 0
    for day, pnl in zip(reversed(seq_days), reversed(seq_pnls)):
        if day == today and st_today.n_traded == 0:
            continue   # nothing to evaluate yet today -- don't count, don't break the streak either
        if pnl < 0:
            streak += 1
        else:
            break

    # -- expected distributions
    day_dist = expected_day_dist(history_pnls, st_today.n_traded)
    dist_3d = expected_3day_dist(history_pnls, n_traded_3d)

    expected_strand = (
        float(np.mean([days[dy].n_stranded / days[dy].n_traded for dy in history_days[-ROLLING_WINDOW_DAYS:]
                       if days[dy].n_traded > 0]))
        if n_live_days >= MIN_LIVE_DAYS_FOR_EMPIRICAL else EXPECTED_STRAND_RATE_PRIOR
    )

    p5_day, p1_day = day_dist.pct(5), day_dist.pct(1)
    p5_3d = dist_3d.pct(5)
    p_neg = day_dist.p_negative()
    p5straight = p_neg ** CONSEC_NEG_DAYS_RED

    red_reasons: list[str] = []
    amber_reasons: list[str] = []

    if today_pnl < p1_day:
        red_reasons.append(f"today's P&L {today_pnl:+.4f} < 1st pct {p1_day:+.4f} ({day_dist.mode})")
    elif today_pnl < p5_day:
        amber_reasons.append(f"today's P&L {today_pnl:+.4f} < 5th pct {p5_day:+.4f} ({day_dist.mode})")

    if pnl_3d < p5_3d:
        amber_reasons.append(f"3-day cum P&L {pnl_3d:+.4f} < 5th pct {p5_3d:+.4f} ({dist_3d.mode})")

    if streak >= CONSEC_NEG_DAYS_RED and p5straight < CONSEC_NEG_DAYS_P_MAX:
        red_reasons.append(f"{streak} consecutive negative days (expected P(5-straight)="
                            f"{p5straight:.4f} < {CONSEC_NEG_DAYS_P_MAX})")

    if n_traded_3d >= MIN_TRADED_FOR_STRAND_CHECK and strand_rate_3d > STRAND_RED_MULTIPLE * expected_strand:
        red_reasons.append(f"3-day strand rate {strand_rate_3d:.1%} > {STRAND_RED_MULTIPLE:.0f}x "
                            f"expected {expected_strand:.1%}")

    status = EXIT_RED if red_reasons else (EXIT_AMBER if amber_reasons else EXIT_OK)

    return {
        "status": status,
        "today": today,
        "asset": asset,
        "today_pnl": today_pnl,
        "today_n_traded": st_today.n_traded,
        "pnl_3d": pnl_3d,
        "n_traded_3d": n_traded_3d,
        "streak_neg_days": streak,
        "strand_rate_3d": strand_rate_3d,
        "expected_strand_rate": expected_strand,
        "n_live_days": n_live_days,
        "day_mode": day_dist.mode,
        "dist_3d_mode": dist_3d.mode,
        "p5_day": p5_day,
        "p1_day": p1_day,
        "p5_3d": p5_3d,
        "p_neg": p_neg,
        "p5straight": p5straight,
        "red_reasons": red_reasons,
        "amber_reasons": amber_reasons,
    }


def format_message(r: dict) -> str:
    tag = {EXIT_OK: "OK", EXIT_AMBER: "SEV-AMBER", EXIT_RED: "SEV-RED"}[r["status"]]
    modes = {r["day_mode"], r["dist_3d_mode"]}
    prior_flag = " [prior-seeded]" if "prior-seeded" in modes else ""
    head = (f"[pnl_guard {tag}]{prior_flag} asset={r['asset']} day={r['today']} "
            f"today_pnl={r['today_pnl']:+.4f} (n={r['today_n_traded']}) "
            f"3d_cum={r['pnl_3d']:+.4f} (n={r['n_traded_3d']}) "
            f"streak_neg={r['streak_neg_days']}d "
            f"strand_3d={r['strand_rate_3d']:.1%} (exp {r['expected_strand_rate']:.1%}) "
            f"n_live_days={r['n_live_days']} "
            f"[day p5={r['p5_day']:+.4f} p1={r['p1_day']:+.4f} mode={r['day_mode']}] "
            f"[3d p5={r['p5_3d']:+.4f} mode={r['dist_3d_mode']}]")
    reasons = r["red_reasons"] if r["status"] == EXIT_RED else r["amber_reasons"]
    if reasons:
        head += " :: " + "; ".join(reasons)
    return head


# ==================================================================================================
# CLI
# ==================================================================================================

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fixture", default=os.environ.get("PNL_GUARD_FIXTURE"),
                     help="JSON file of winrec-row fixtures; bypasses live-state entirely (testing only)")
    ap.add_argument("--as-of", default=os.environ.get("PNL_GUARD_AS_OF"),
                     help="Override 'today' (UTC, YYYY-MM-DD). Defaults to real UTC now.")
    ap.add_argument("--asset", default="btc")
    args = ap.parse_args(argv)

    try:
        if args.fixture:
            rows = load_fixture_rows(args.fixture)
        else:
            fetch_live_state()
            rows = load_live_winrec_rows(args.asset)

        today = args.as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        days = bucket_by_day(rows, args.asset)
        result = evaluate(days, today, args.asset)
        msg = format_message(result)
        print(msg)
        return result["status"]
    except Exception as e:
        # Guard failures must not look like a RED/AMBER alert, and must not crash the workflow --
        # health.yml also wraps the invocation in `|| true` as belt-and-suspenders, but the script
        # itself should degrade gracefully first (matches health_check.py's own convention).
        print(f"[pnl_guard OK] guard could not evaluate this cycle ({type(e).__name__}: {e}) -- "
              f"treating as non-fatal, no alert", file=sys.stderr)
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
