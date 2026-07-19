"""health_check.py -- INDEPENDENT durability monitor for ALL data-collection streams.

WHY THIS EXISTS (the operator's ask: 24/7 collection with no manual prompting to confirm it works).
The collect chain is self-healing (self-chain + 3 crons/hr + heartbeat), but nothing TOLD anyone when
it broke -- you had to run watch_continuity.py yourself. This is the self-reporting layer: it runs on
its OWN cron in a SEPARATE workflow (health.yml), so if the collect chain dies entirely, THIS still
runs and pings you. It is git-based (reads the committed data trail on the gha-data branch) -- no auth,
no API blob, cheap.

WHAT IT CHECKS (each must be fresh or it alerts):
  - overall gha_data freshness (last commit age) -- the master "is collection alive" signal
  - each required per-asset Kalshi stream present in the latest cycle (btc/eth/sol/xrp x book/trades/fills)
  - the Polymarket cross-venue stream (pmkt_btc_updown)
  - the A/B ledger fragments (the prospective-test pipeline)

MODES:
  python health_check.py            # print a compact report; exit 0 healthy / 2 stale-critical / 1 warn
  python health_check.py --alert    # + Telegram alert IF not healthy (silent when healthy = no spam)
  python health_check.py --heartbeat# + Telegram one-line OK summary (call once/day for passive assurance)

Thresholds: a collect cycle writes ~every 45 min. >130 min stale (two missed cycles) = CRITICAL.
"""
from __future__ import annotations

import subprocess
import sys
import time

BRANCH = "gha-data"
REMOTE = f"origin/{BRANCH}"
STALE_CRIT_MIN = 130          # two missed collect cycles -> collection is down
CYCLE_WINDOW_MIN = 140        # files touched within this window = "the latest cycle"

# COLLECTED streams that MUST appear in the latest cycle (basename fragments, asset-expanded below).
# NOTE: the A/B ledger is intentionally NOT here -- it is DERIVED from book/trades by strategy-alert.yml
# downstream, not a collected artifact, so it never lands on the gha-data branch.
ASSETS = ("btc", "eth", "sol", "xrp")
PER_ASSET = ("book", "trades", "fills")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def fetch() -> None:
    subprocess.run(["git", "fetch", "origin", BRANCH, "-q"], capture_output=True, text=True)


def last_commit_age_min() -> float | None:
    line = git("log", "-1", "--format=%ct", REMOTE, "--", "gha_data/").strip()
    if not line:
        return None
    return (time.time() - int(line)) / 60.0


def files_in_recent_commits(window_min: int) -> set[str]:
    """Basenames of files committed within window_min (the latest collect cycle)."""
    since = int(time.time() - window_min * 60)
    log = git("log", f"--since=@{since}", "--name-only", "--format=", REMOTE, "--", "gha_data/")
    out = set()
    for ln in log.splitlines():
        ln = ln.strip()
        if ln:
            out.add(ln.rsplit("/", 1)[-1])
    return out


def check() -> tuple[int, list[str]]:
    """Return (status, lines). status: 0 healthy, 1 warn (partial), 2 critical (collection down)."""
    fetch()
    lines: list[str] = []
    age = last_commit_age_min()
    if age is None:
        return 2, ["CRITICAL: no gha_data commits found at all on the data branch"]

    lines.append(f"last data commit: {age:.0f} min ago")
    if age > STALE_CRIT_MIN:
        return 2, lines + [f"CRITICAL: collection STALLED -- {age:.0f} min > {STALE_CRIT_MIN} "
                           f"(two missed cycles). Self-chain + crons did not re-arm."]

    recent = files_in_recent_commits(CYCLE_WINDOW_MIN)
    missing: list[str] = []
    for a in ASSETS:
        for s in PER_ASSET:
            if not any(f.startswith(f"{s}_kalshi_{a}15m") for f in recent):
                missing.append(f"{s}:{a}")
    pmkt_ok = any(f.startswith("pmkt_btc_updown") for f in recent)
    if not pmkt_ok:
        missing.append("pmkt_btc_updown (cross-venue)")

    if missing:
        return 1, lines + [f"WARN: fresh overall but {len(missing)} stream(s) absent from the latest "
                           f"cycle: {', '.join(missing)}"]
    lines.append(f"all streams fresh: {len(ASSETS)*len(PER_ASSET)} kalshi + pmkt")
    return 0, lines


def main() -> int:
    status, lines = check()
    tag = {0: "HEALTHY", 1: "WARN", 2: "CRITICAL"}[status]
    report = f"[health {tag}] " + " | ".join(lines)
    print(report)

    if "--alert" in sys.argv and status != 0:
        try:
            import notify
            notify.alert_sync(f"⚠️ data collection {tag}\n{chr(10).join(lines)}\n"
                              f"(health.yml monitor; collect chain may need a kick)")
        except Exception as e:
            print(f"alert send failed: {e}")
    if "--heartbeat" in sys.argv and status == 0:
        try:
            import notify
            notify.alert_sync(f"✅ data collectors healthy — {lines[-1]}")
        except Exception as e:
            print(f"heartbeat send failed: {e}")
    return status


if __name__ == "__main__":
    sys.exit(main())
