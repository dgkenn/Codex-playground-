#!/usr/bin/env python3
"""Continuity health-check + probe for the unattended paper-data collector.

The collector runs on GitHub Actions: paper-collect.yml (scheduled twice hourly, queued
back-to-back via the concurrency group) collects multi-asset shadow data and commits it to the
dedicated `gha-data` branch -- NOT the code branch (the old chain/watchdog design is retired).

This tool is GIT-BASED on purpose: it reads the committed data trail rather than the
GitHub REST API, so it has no auth/rate-limit dependency and works from any clone
(the unauthenticated REST API is only 60 req/hr and is shared per egress IP).

  python watch_continuity.py            # one-shot health summary (default)
  python watch_continuity.py --probe    # loop; exit 0 once a NEW autonomous collect
                                        # run commits data (= self-perpetuating proof)

Each GHA collect run tags its commits/heartbeat with a unique id: "r<run_id>" for
paper-collect, "wd<run_id>" for the watchdog. A tag NOT in BASELINE appearing in the
commit log is proof of an autonomous (chain/schedule/watchdog) re-trigger.
"""
import re, subprocess, sys, time

BRANCH = "gha-data"               # DATA lands here (the old code-branch watch was permanently stale)
REMOTE = f"origin/{BRANCH}"
# Runs that exist at the time continuity was first instrumented; any collect/watchdog
# tag beyond these appearing later proves an autonomous re-trigger.
BASELINE = {"r27098173318", "r27100456475"}
TAG_RE = re.compile(r"\b(r\d{6,}|wd\d{6,})\b")


def git(*args):
    return subprocess.run(["git", *args], cwd=".", capture_output=True, text=True).stdout


def emit(msg):
    print(f"{time.strftime('%H:%MZ', time.gmtime())} {msg}", flush=True)


def fetch():
    subprocess.run(["git", "fetch", "origin", BRANCH, "-q"], capture_output=True, text=True)


def tags_seen():
    log = git("log", "--oneline", REMOTE)
    return set(TAG_RE.findall(log))


def last_data_commit():
    line = git("log", "-1", "--format=%ct|%cr|%s", REMOTE, "--", "gha_data/").strip()
    return line.split("|", 2) if line else None


def status():
    fetch()
    all_tags = tags_seen()
    autonomous = sorted(all_tags - BASELINE)
    lc = last_data_commit()
    if lc:
        ts, rel, subj = lc
        age_min = (time.time() - int(ts)) / 60
        emit(f"last gha_data commit: {rel} ({age_min:.0f} min ago) -- {subj}")
        if age_min > 130:
            emit(f"WARNING: data is {age_min:.0f} min stale (>130 = two missed runs) -- check the "
                 f"Actions tab; the HEARTBEAT_URL dead-man (healthchecks.io) should also have fired")
    else:
        emit("no gha_data commits found yet")
    emit(f"collect/watchdog run tags seen: {sorted(all_tags)}")
    if autonomous:
        emit(f"ROUND: autonomous run tag(s) beyond the seed: {autonomous} -> self-perpetuating confirmed")
    else:
        emit("not yet proven round: no run tag beyond the baseline seed has appeared")


def probe():
    while True:
        fetch()
        new = sorted(tags_seen() - BASELINE)
        if new:
            emit(f"AUTONOMOUS run committed gha data: tag={new[0]} -- self-perpetuating continuity VERIFIED")
            return 0
        time.sleep(60)


if __name__ == "__main__":
    sys.exit(probe() if "--probe" in sys.argv else (status() or 0))
