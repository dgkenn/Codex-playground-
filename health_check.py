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

import re
import subprocess
import sys
import time

BRANCH = "gha-data"
REMOTE = f"origin/{BRANCH}"
STALE_CRIT_MIN = 130          # two missed collect cycles -> collection is down
CYCLE_WINDOW_MIN = 140        # files touched within this window = "the latest cycle"
MIN_PAYLOAD_BYTES = 200        # below this, a stream file is a placeholder/truncated write, not data
                                # (copy_multi_results/*.json held literal "{}" for a MONTH -- freshness
                                # alone never caught it; size is the cheap orthogonal signal)

# COLLECTED streams that MUST appear in the latest cycle (basename fragments, asset-expanded below).
# NOTE: the A/B ledger is intentionally NOT here -- it is DERIVED from book/trades by strategy-alert.yml
# downstream, not a collected artifact, so it never lands on the gha-data branch.
ASSETS = ("btc", "eth", "sol", "xrp")
PER_ASSET = ("book", "trades", "fills")
# (label, basename-prefix) for every required stream, used by both the presence check and the
# content-validity (payload-size) check below.
STREAMS = [(f"{s}:{a}", f"{s}_kalshi_{a}15m") for a in ASSETS for s in PER_ASSET] \
        + [("pmkt_btc_updown (cross-venue)", "pmkt_btc_updown")]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def fetch(window_min: int = CYCLE_WINDOW_MIN) -> None:
    """TIME-bounded shallow fetch: --shallow-since keeps it fast (bounded object count on a branch
    with a huge total history) while still yielding REAL per-commit diffs for `git log --name-only`
    (unlike a plain --depth=1, which flattens the sole visible commit against an empty tree and would
    make every file in the whole tree look "recent" forever -- silently disabling the missing-stream
    check). The padding beyond window_min guarantees every commit inside our actual lookback window has
    its real parent present too. This also materializes the tip tree's BLOBS (not just commit/tree
    metadata), which is what makes the content-validity size check below possible without a checkout."""
    since_ts = int(time.time() - (window_min + STALE_CRIT_MIN + 60) * 60)
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since_ts))
    r = subprocess.run(["git", "fetch", "origin", BRANCH, f"--shallow-since={since}", "-q"],
                        capture_output=True, text=True)
    if r.returncode != 0:                          # e.g. repo already deeper than `since` -- harmless
        subprocess.run(["git", "fetch", "origin", BRANCH, "-q"], capture_output=True, text=True)


def last_commit_age_min() -> float | None:
    line = git("log", "-1", "--format=%ct", REMOTE, "--", "gha_data/").strip()
    if not line:
        return None
    return (time.time() - int(line)) / 60.0


def files_in_recent_commits_detailed(window_min: int) -> list[str]:
    """Full repo-relative paths of files committed within window_min, newest-commit-first
    (duplicates possible across commits; that's fine, callers only care about presence/latest)."""
    since = int(time.time() - window_min * 60)
    log = git("log", f"--since=@{since}", "--name-only", "--format=", REMOTE, "--", "gha_data/")
    return [ln.strip() for ln in log.splitlines() if ln.strip()]


def files_in_recent_commits(window_min: int) -> set[str]:
    """Basenames of files committed within window_min (the latest collect cycle)."""
    return {p.rsplit("/", 1)[-1] for p in files_in_recent_commits_detailed(window_min)}


def latest_paths_for_streams(paths_newest_first: list[str], streams) -> dict[str, str]:
    """For each (label, prefix) in `streams`, the newest matching full path, if any. Relies on
    `paths_newest_first` being newest-commit-first (see files_in_recent_commits_detailed)."""
    out: dict[str, str] = {}
    for p in paths_newest_first:
        base = p.rsplit("/", 1)[-1]
        for label, prefix in streams:
            if label not in out and base.startswith(prefix):
                out[label] = p
    return out


def blob_sizes(paths: list[str]) -> dict[str, int]:
    """Byte size of each path's blob at REMOTE's tip, via `git ls-tree -r -l` (no checkout). Falls
    back to `git cat-file -s` per-path if ls-tree reports an unresolved/promised size ("-") -- the
    stream list is tiny (~13 files) so a handful of extra round trips is cheap."""
    if not paths:
        return {}
    out = git("ls-tree", "-r", "-l", REMOTE, "--", *paths)
    sizes: dict[str, int] = {}
    shas: dict[str, str] = {}
    for ln in out.splitlines():
        m = re.match(r"^\S+\s+\S+\s+(\S+)\s+(\S+)\t(.+)$", ln)
        if not m:
            continue
        sha, size_s, path = m.group(1), m.group(2), m.group(3)
        shas[path] = sha
        if size_s.isdigit():
            sizes[path] = int(size_s)
    for p in paths:
        if p not in sizes and p in shas:
            s = git("cat-file", "-s", shas[p]).strip()
            if s.isdigit():
                sizes[p] = int(s)
    return sizes


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

    recent_paths = files_in_recent_commits_detailed(CYCLE_WINDOW_MIN)
    recent = {p.rsplit("/", 1)[-1] for p in recent_paths}
    missing: list[str] = []
    for label, prefix in STREAMS:
        if not any(f.startswith(prefix) for f in recent):
            missing.append(label)

    # CONTENT-VALIDITY: presence alone isn't enough -- a stream can commit a file every cycle that
    # is just an empty/placeholder payload (this happened for real: copy_multi_results/*.json held
    # literal "{}" for a MONTH and freshness checks passed the whole time). For every required
    # stream that IS present, check its latest file's blob size and flag near-empty ones.
    latest = latest_paths_for_streams(recent_paths, STREAMS)
    sizes = blob_sizes(list(latest.values()))
    empty = sorted(label for label, p in latest.items() if sizes.get(p, 0) < MIN_PAYLOAD_BYTES)

    if empty:
        return 2, lines + [f"CRITICAL: EMPTY-PAYLOAD -- latest file < {MIN_PAYLOAD_BYTES}B for "
                           f"{len(empty)} stream(s) (placeholder/truncated write; presence/freshness "
                           f"alone won't catch this): {', '.join(empty)}"]
    if missing:
        return 1, lines + [f"WARN: fresh overall but {len(missing)} stream(s) absent from the latest "
                           f"cycle: {', '.join(missing)}"]
    lines.append(f"all streams fresh & content-valid: {len(ASSETS)*len(PER_ASSET)} kalshi + pmkt")
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
