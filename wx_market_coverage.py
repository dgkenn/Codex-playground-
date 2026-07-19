#!/usr/bin/env python3
"""wx_market_coverage.py -- are we trading every ACTIVE Kalshi daily-CLI temperature market? (volume check)

The cleanest way to grow volume at the SAME edge and SAME risk is to trade more cities of the identical
product. This enumerates Kalshi's live "Climate and Weather" daily high/low temp series, keeps only those
with OPEN events (deprecated series have none), and flags any active one the bot doesn't cover -- a free
same-EV volume add. Run it periodically: if Kalshi lists a new city, this catches it. Read-only public API.

Finding on 2026-07-19: we cover all 20 active daily cities (high+low). The 13 "uncovered" series (KXLOW*
without the T, KXHIGHHOU vs our KXHIGHTHOU, etc.) all have 0 open events = deprecated naming variants. The
one hourly temp series (KXHIGHNYD) settles on The Weather Company, not NWS CLI -> our lock edge can't track
it. So the daily-CLI edge is volume-MAXED on market count; the remaining volume levers are DEPTH_CAP (fill
more per fire if books are deep -- see kwx-depthprobe) and the paid Synoptic 1-min feed (~2x fires).

--watch mode (kwx-marketwatch cron): the finding above is a SNAPSHOT -- nobody re-runs it, so a brand-new
Kalshi city (== roughly proportional new depth-capped capacity) would sit unnoticed for weeks. `--watch`
turns the same enumeration into a change detector: it diffs the live series list against a COMMITTED state
file (wx_known_series.json -- committed so the baseline survives ephemeral CI runners and the diff is
reviewable in git history) and Telegram-alerts on any NEW series, any known series DISAPPEARING from the
listing (delisting = capacity loss), or a known deprecated variant coming ALIVE (open events > 0 -- that is
new capacity too, and it is exactly how the 13 dead naming variants would return without being "new").
The very first run (no state file) seeds the baseline silently -- 30+ "new series" alerts about markets
that existed all along would just train us to ignore the alert. Read-only public API; never trades.
"""
import datetime as dt
import json, os, ssl, sys, urllib.request, urllib.parse
import kwx_runner as R
import kwx_notify

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KB = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
# Committed baseline of every daily temp series we have ever seen (ticker -> title/status/first_seen).
# Overridable via env so tests can run against a scratch file without touching the real baseline.
STATE_PATH = os.environ.get("KWX_KNOWN_SERIES_PATH", os.path.join(HERE, "wx_known_series.json"))


def _get(u, to=25):
    try:
        return json.load(urllib.request.urlopen(
            urllib.request.Request(u, headers={"Accept": "application/json"}), timeout=to, context=_CTX))
    except Exception as e:
        return {"__err__": type(e).__name__}


def _list_daily_temp_series():
    """One shared discovery path for both modes: all daily KXHIGH*/KXLOW* series in Climate and Weather.
    Returns None on any fetch problem (including an implausible empty list) so --watch can refuse to diff
    against garbage -- a transient API outage must never read as 'every city got delisted'."""
    d = _get(f"{KB}/series?category={urllib.parse.quote('Climate and Weather')}")
    if "__err__" in d:
        print(f"!! series listing fetch failed ({d['__err__']}) -- no data this run")
        return None
    temp = [s for s in d.get("series", [])
            if s["ticker"].startswith(("KXHIGH", "KXLOW")) and s.get("frequency") == "daily"]
    if not temp:
        print("!! series listing returned ZERO daily temp series -- implausible (Kalshi lists 30+); "
              "treating as an API glitch, not a mass delisting")
        return None
    return temp


def _open_events(ticker):
    """Number of OPEN events for a series (0 = deprecated variant), or None if the probe errored --
    callers must treat None as 'unknown' and keep the previous status rather than flag a change."""
    ev = _get(f"{KB}/events?series_ticker={ticker}&status=open&limit=1")
    if "__err__" in ev:
        return None
    return len(ev.get("events", []))


def main():
    ours = set(R.CITY.keys()) | set(R.CITY_LOW_SERIES.values())
    temp = _list_daily_temp_series() or []
    print(f"Kalshi daily temp series: {len(temp)} | we trade: {len(ours)}\n")
    active_missing = []
    for s in temp:
        t = s["ticker"]
        if t in ours:
            continue
        n_open = _open_events(t) or 0
        tag = "ACTIVE -- NOT TRADED (add it!)" if n_open > 0 else "deprecated (0 open events)"
        if n_open > 0:
            active_missing.append(t)
        print(f"  {t:>16} | open_events={n_open} | {s.get('title','')[:38]:38} | {tag}")
    print()
    if active_missing:
        print(f"*** {len(active_missing)} ACTIVE series we should ADD for free same-EV volume: {active_missing}")
    else:
        print("All ACTIVE daily-CLI temp cities are covered -- no free market volume to add (as of last run).")
        print("Remaining volume levers: DEPTH_CAP (kwx-depthprobe) + Synoptic 1-min feed (paid, ~2x fires).")


def _load_state():
    """Baseline dict {ticker: {'title','status','first_seen'}} or None if never seeded."""
    try:
        with open(STATE_PATH) as f:
            return json.load(f)["series"]
    except FileNotFoundError:
        return None


def _save_state(series):
    with open(STATE_PATH, "w") as f:
        json.dump({
            # why committed: the baseline must survive ephemeral CI runners, and a git-diffable state file
            # doubles as an audit log of every listing change Kalshi ever made (when + what).
            "_comment": "kwx-marketwatch baseline: every Kalshi daily temp series ever seen. Do not edit "
                        "by hand; wx_market_coverage.py --watch maintains it (deleting an entry makes the "
                        "next run re-alert it as NEW, which is also how you test the alert path).",
            "series": {t: series[t] for t in sorted(series)},
        }, f, indent=1, sort_keys=False)
        f.write("\n")


def watch():
    """Diff the live series list against the committed baseline; report + Telegram-alert changes.

    Change classes (each one moves capacity, which is the binding constraint on this depth-capped bot):
      NEW        ticker never seen before          -> new city ~= proportional new capacity: act on it
      DELISTED   known ticker gone from listing    -> capacity loss (and if we trade it, config cleanup)
      REVIVED    known 0-open-event variant now has open events -> capacity add via an OLD ticker; without
                 this class the 13 deprecated naming variants (KXHIGHHOU etc.) could come back to life and
                 the NEW-only diff would stay silent forever, since they are already in the baseline
      RETIRED    known active series now has 0 open events -> soft delisting (ticker kept, events stopped)
    Status probes that error return None and we KEEP the old status -- a flaky /events call must not
    fabricate a REVIVED/RETIRED transition. Exit 0 on a clean run (changes are findings, not failures),
    exit 1 only when the API gave us nothing to diff.
    """
    today = dt.date.today().isoformat()
    temp = _list_daily_temp_series()
    if temp is None:
        print("watch: aborting without touching state (will retry next scheduled run)")
        return 1
    ours = set(R.CITY.keys()) | set(R.CITY_LOW_SERIES.values())
    known = _load_state()

    # Probe open-event status for every listed series (~35 cheap public GETs, weekly): status is what
    # separates a tradable listing from a dead naming variant, for seeding and for REVIVED/RETIRED alike.
    live = {}
    for s in temp:
        t = s["ticker"]
        n = _open_events(t)
        live[t] = {"title": s.get("title", ""),
                   "status": ("unknown" if n is None else ("active" if n else "deprecated"))}

    if known is None:
        # FIRST RUN: seed silently. Alerting 30+ long-existing series as "new" would only teach us to
        # ignore the channel; the value of this watcher is that a later alert is ALWAYS a real change.
        for t, v in live.items():
            v["first_seen"] = today
        _save_state(live)
        print(f"watch: seeded baseline with {len(live)} daily temp series -> {os.path.basename(STATE_PATH)}"
              f" (no alerts on the seeding run by design)")
        return 0

    new = sorted(t for t in live if t not in known)
    gone = sorted(t for t in known if t not in live)
    revived = sorted(t for t in live if t in known
                     and known[t].get("status") == "deprecated" and live[t]["status"] == "active")
    retired = sorted(t for t in live if t in known
                     and known[t].get("status") == "active" and live[t]["status"] == "deprecated")

    lines = []
    for t in new:
        covered = "already traded (?!)" if t in ours else "NOT in bot config -> add for new capacity"
        lines.append(f"NEW listing: {t} [{live[t]['status']}] {live[t]['title'][:40]} -- {covered}")
    for t in gone:
        was = known[t].get("status", "?")
        hit = " (WE TRADE IT -- capacity loss + remove from config)" if t in ours else ""
        lines.append(f"DELISTED: {t} [was {was}] {known[t].get('title', '')[:40]}{hit}")
    for t in revived:
        lines.append(f"REVIVED: {t} now has open events (was a dead variant) -- capacity add, check basis")
    for t in retired:
        hit = " (WE TRADE IT -- capacity loss)" if t in ours else ""
        lines.append(f"RETIRED: {t} has 0 open events now (was active){hit}")

    if lines:
        report = "\n".join(lines)
        print(f"watch: {len(lines)} listing change(s) vs baseline of {len(known)}:\n" + report)
        # alert_sync (not the daemon-thread alert()): this is a short-lived CLI -- the process would exit
        # before a daemon thread finishes the HTTPS POST. Same helper module, same no-op-without-env,
        # same never-raises contract; returns False when TELEGRAM_* is unset.
        sent = kwx_notify.alert_sync("📣 K-WX market-watch: Kalshi daily-temp listings changed\n" + report
                                     + "\n(capacity is depth-capped per city -> listings ARE capacity)")
        print(f"watch: telegram alert {'sent' if sent else 'skipped (TELEGRAM_* not set) or failed'}")
    else:
        print(f"watch: no changes -- {len(live)} series match the baseline "
              f"({sum(1 for v in live.values() if v['status'] == 'active')} active)")

    # Merge live view back into state: adds NEW, drops DELISTED (a re-listing later re-alerts as NEW,
    # which is what we want), updates status transitions. first_seen is preserved; an errored status
    # probe ('unknown') keeps the previous status so it cannot flap.
    merged = {}
    for t, v in live.items():
        old = known.get(t, {})
        status = old.get("status", v["status"]) if v["status"] == "unknown" else v["status"]
        merged[t] = {"title": v["title"] or old.get("title", ""), "status": status,
                     "first_seen": old.get("first_seen", today)}
    if merged != known:
        _save_state(merged)
        print(f"watch: state updated ({len(known)} -> {len(merged)} series)")
    return 0


if __name__ == "__main__":
    sys.exit(watch()) if "--watch" in sys.argv[1:] else main()
