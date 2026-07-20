#!/usr/bin/env python3
"""kwx_daily_digest.py -- the DAILY 📊 end-of-day Telegram summary kwx_notify's docstring promised but
nothing ever wired. One message a day, after all US LST market days settle, so every go/no-go decision
(paper gate -> $10 canary -> $50 -> scale) is visible without manually digging through logs:

  * GATE    : n settled / 30 required, win rate, EV/ct, day-clustered t -- computed by REUSING
              kwx_paper_gate._report_metrics (the exact numbers the gate decision runs on, not a re-derive)
  * FIRES   : last-24h fires from kwx_runner_plan.jsonl (count, cities, prices paid)
  * FEEDS   : per-station freshness of the FREE feeds (weather.gov + METAR), reusing kwx_runner's
              staleness guard -- flags a station only when ALL its free feeds are stale/empty, i.e. the
              exact condition under which the consensus quorum would refuse to trade it
  * VERDICT : the gate's READY-FOR-CANARY / ACCRUING verdict string (same logic as kwx_gate_status.txt)

READ-ONLY + STATELESS: fetches logs from disk when present (runner host) or from the trading branch via
the public GitHub contents API (fresh workflow checkout -- the logs are gitignored locally and committed
only by kwx-live), never writes repo state, never trades, never touches KWX_SWITCH / .kwx_halt.
NO-OP SAFE: without TELEGRAM_* env the send is skipped (kwx_notify no-ops) but the digest text is STILL
printed to stdout and we exit 0 -- the workflow log is the fallback channel.

Usage: python kwx_daily_digest.py
"""
import os, json, base64, ssl, tempfile, datetime as dt, urllib.request, urllib.parse

import kwx_forward as F
import kwx_paper_gate as PG
import kwx_runner as R
import kwx_notify

# same repo/branch convention as kwx_telegram.status_text (the pattern this fetch copies)
REPO = os.environ.get("KWX_REPO", "dgkenn/codex-playground-")
BRANCH = os.environ.get("BRANCH", "claude/coding-bot-ab-test-results-ffmhxw")
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
MAX_FIRE_LINES = 8      # keep the message glanceable (and well under Telegram's 4096-char cap)


# ---------------- log acquisition (local file OR the branch's committed copy) ----------------
def _fetch_branch_file(name):
    """Best-effort text of a repo file from the trading branch via the public contents API -- same pattern
    as kwx_telegram.status_text(). Unauthenticated works (repo is public); GH_TOKEN used only if present
    (kinder rate limits inside Actions). Returns None on any failure -- the digest must never crash."""
    url = f"https://api.github.com/repos/{REPO}/contents/{urllib.parse.quote(name)}?ref={urllib.parse.quote(BRANCH, safe='')}"
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                             timeout=20, context=_CTX))
        return base64.b64decode(d.get("content") or "").decode() or None
    except Exception:
        return None


def _rows_local_or_branch(path):
    """jsonl rows from a log that may be on disk (runner host) or only committed on the branch (fresh
    checkout: these logs are gitignored and force-added by kwx-live). Empty list when neither has it --
    fresh-repo case, which the digest reports as 'accruing', not an error."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return F._load_jsonl(path)
    txt = _fetch_branch_file(os.path.basename(path))
    if not txt:
        return []
    rows = []
    for l in txt.splitlines():
        try:
            rows.append(json.loads(l))
        except Exception:
            pass
    return rows


# ---------------- section 1: gate progress (REUSE kwx_paper_gate, don't recompute) ----------------
def gate_metrics():
    """Gate stats via kwx_paper_gate._report_metrics -- the SAME function the gate decision runs on, so the
    digest can never drift from the gate. If the settled log isn't on disk, pull the branch copy into a
    temp file and point kwx_forward.SETTLED at it for the call (restored after)."""
    if os.path.exists(F.SETTLED) and os.path.getsize(F.SETTLED) > 0:
        return PG._report_metrics()
    txt = _fetch_branch_file(os.path.basename(F.SETTLED))
    if not txt:
        return None                       # nothing settled anywhere yet -> accruing
    fd, tmp = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        f.write(txt)
    old = F.SETTLED
    F.SETTLED = tmp
    try:
        return PG._report_metrics()
    finally:
        F.SETTLED = old
        os.unlink(tmp)


def verdict_line(m):
    """The gate's verdict string -- IDENTICAL logic to kwx_paper_gate._write_status (not called directly
    because that would clobber kwx_gate_status.txt with a bogus 'last poll' line; PASS bar is shared so the
    two can only diverge if _write_status's expression itself changes)."""
    P = PG.PASS
    if not m:
        return (f"ACCRUING (no settled paper fires yet; bar: win>={P['win']:.0%}, "
                f"EV>=+{P['ev']:.2f}, t>={P['t']}, n>={P['n']})")
    passed = (m["win"] >= P["win"] and m["ev"] >= P["ev"] and
              (m["t"] >= P["t"] or m["t"] != m["t"]) and m["n"] >= P["n"])   # t!=t = NaN guard (few days)
    return ("READY-FOR-CANARY (live==tested)" if passed and m["n"] >= P["n"] and m["t"] >= P["t"]
            else "ACCRUING (need n>=30 and t>=3)" if m["n"] < P["n"] or (m["t"] < P["t"])
            else "REVIEW -- win/EV below bar (live may differ from tested)")


# ---------------- section 2: fires in the last 24h ----------------
def fires_last_24h():
    """Plan-log rows fired in the last 24h (ts is epoch-ms, written by kwx_runner.poll_once)."""
    rows = _rows_local_or_branch(R.PLAN_LOG)
    cutoff_ms = (dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=24)).timestamp() * 1000
    return [r for r in rows if isinstance(r.get("ts"), (int, float)) and r["ts"] >= cutoff_ms]


# ---------------- section 3: free-feed freshness ----------------
def feed_health():
    """(all_stale_stations, n_stations_checked). Reuses kwx_runner's staleness guard (_feed_is_stale /
    STALE_MIN=45) against the two FREE feeds (weather.gov 5-min + METAR). A station is flagged only when
    ALL its free feeds are stale or empty -- exactly when MultiFeedConsensus would drop it from the quorum
    and stop trading it. Cheap: one obs fetch per station per feed, short-circuiting on the first fresh."""
    feeds = [R._WGOV, R._METAR]
    now_utc = dt.datetime.now(tz=dt.timezone.utc)
    bad, seen = [], set()
    for _series, (station, offset) in R.CITY.items():
        if station in seen:               # CITY maps series->station; stations are what feeds serve
            continue
        seen.add(station)
        lst_date = (now_utc + dt.timedelta(hours=offset)).date().isoformat()
        fresh = False
        for f in feeds:
            try:
                r = f.running_extreme(station, lst_date, offset, "max")
            except Exception:
                r = None
            obs = (r or {}).get("obs") or []
            # empty obs is NOT fresh (note _feed_is_stale returns False on empty -- it guards parse
            # failures, not absence), so require both: some obs AND newest within STALE_MIN.
            if obs and not R._feed_is_stale(obs):
                fresh = True
                break
        if not fresh:
            bad.append(station)
    return sorted(bad), len(seen)


# ---------------- compose + send ----------------
def compose():
    now = dt.datetime.now(tz=dt.timezone.utc)
    P = PG.PASS
    lines = [f"📊 KWX DAILY DIGEST — {now:%Y-%m-%d %H:%M}Z"]

    # gate progress (the numbers every go/no-go decision hangs on)
    try:
        m = gate_metrics()
    except Exception as e:                # a flaky settle fetch must not kill the whole digest
        m = None
        lines.append(f"gate: metrics unavailable ({type(e).__name__})")
    if m:
        lines.append(f"gate: {m['n']}/{P['n']} settled over {m['days']}d")
        lines.append(f"  win {m['win']:.1%} (bar {P['win']:.0%}) | EV {m['ev']:+.3f}/ct "
                     f"(bar +{P['ev']:.2f}) | day-clustered t {m['t']:.2f} (bar {P['t']})")
    else:
        lines.append(f"gate: 0/{P['n']} settled — accruing")

    # fires in the last 24h (count, cities, prices paid)
    try:
        recent = fires_last_24h()
    except Exception:
        recent = []
    if recent:
        cities = sorted({r.get("station", "?") for r in recent})
        lines.append(f"fires 24h: {len(recent)} ({', '.join(cities)})")
        for r in recent[:MAX_FIRE_LINES]:
            lines.append(f"  • {r.get('ticker', '?')} {str(r.get('side', '?')).upper()}"
                         f"@{r.get('cap_c', '?')}¢ x{r.get('requested', '?')}")
        if len(recent) > MAX_FIRE_LINES:
            lines.append(f"  … +{len(recent) - MAX_FIRE_LINES} more")
    else:
        lines.append("fires 24h: none")

    # near-misses (locks the obs stream confirmed but we couldn't buy). THE diagnostic for zero-fire
    # days: many near-misses = detection too slow / books dead (the paid-feed question), zero of both =
    # genuinely quiet weather. Fail-soft like the other monitor lines.
    try:
        cutoff = (dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=24)).timestamp() * 1000
        misses = []
        with open(R.NEAR_MISS_LOG) as fh:
            for ln in fh:
                try:
                    rec = json.loads(ln)
                    if rec.get("ts", 0) >= cutoff:
                        misses.append(rec)
                except Exception:
                    continue
        if misses:
            reasons = {}
            for r in misses:
                reasons[r.get("reason", "?")] = reasons.get(r.get("reason", "?"), 0) + 1
            rtxt = ", ".join(f"{k}×{v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]))
            lines.append(f"near-misses 24h: {len(misses)} ({rtxt})")
            for r in misses[:3]:
                lines.append(f"  ◦ {r.get('ticker', '?')} {str(r.get('side', '?')).upper()} "
                             f"ask={r.get('ask_c')}¢ cushion={r.get('cushion_f')}°F")
        else:
            lines.append("near-misses 24h: none")
    except FileNotFoundError:
        lines.append("near-misses 24h: none logged yet")
    except Exception as e:
        lines.append(f"near-misses: check unavailable ({type(e).__name__})")

    # free-feed health (a station with NO fresh free feed can't fire tomorrow either)
    try:
        bad, total = feed_health()
        lines.append(f"feeds: all {total} stations fresh"
                     if not bad else f"feeds: STALE at {', '.join(bad)} (all free feeds stale/empty)")
    except Exception as e:
        lines.append(f"feeds: check unavailable ({type(e).__name__})")

    lines.append(f"VERDICT: {verdict_line(m)}")

    # settlement-drift monitor (wx_settlement_drift.py) -- optional dependency: it may not be merged
    # onto this branch yet, so the import itself is guarded, not just the call. Fails soft either way:
    # the digest must never crash because a study module is missing or errors on stale/partial logs.
    try:
        import wx_settlement_drift as SD
        status = SD.check()
        lines.append(f"drift: {status}")
    except ImportError:
        lines.append("drift: drift monitor not installed")
    except Exception as e:
        lines.append(f"drift: check unavailable ({type(e).__name__})")

    # fill-quality monitor (kwx_fill_quality.py) -- reuse its own verdict function so this line can never
    # drift from what `python kwx_fill_quality.py` itself would report. fetch_trades=False keeps this
    # cheap and offline (no public-trade-tape calls) since it only needs to run once a day.
    try:
        import kwx_fill_quality as FQ
        rows, _n_blocked = FQ.build_rows(fetch_trades=False)
        verdict, detail = FQ.compute_verdict(rows)
        lines.append(f"fill-quality: {verdict} (n={detail.get('n', len(rows))})")
    except ImportError:
        lines.append("fill-quality: fill-quality monitor not installed")
    except Exception as e:
        lines.append(f"fill-quality: check unavailable ({type(e).__name__})")

    # early-lock forward-price decision (wx_earlylock_decision.py) -- optional dependency, same guarded-import
    # pattern as drift/fill-quality above: it may not be merged onto this branch yet, and this line must never
    # take the whole digest down because that PAPER-only sleeve's log is thin, missing, or mid-accrual.
    try:
        import wx_earlylock_decision as EL
        lines.append(f"earlylock: {EL.one_line()}")
    except ImportError:
        lines.append("earlylock: decision layer not installed")
    except Exception as e:
        lines.append(f"earlylock: check unavailable ({type(e).__name__})")

    # $4k/mo goal-status digest (kwx_goal_status.py) -- same guarded-import pattern as drift/fill-quality/
    # earlylock above: fails soft so a missing or broken goal-status module never takes the digest down.
    try:
        import kwx_goal_status as GS
        lines.append(f"goal: {GS.summary_line()}")
    except ImportError:
        lines.append("goal: goal-status monitor not installed")
    except Exception as e:
        lines.append(f"goal: check unavailable ({type(e).__name__})")

    return "\n".join(lines)


def main():
    text = compose()
    print(text, flush=True)               # ALWAYS print: the workflow log is the no-Telegram fallback
    # alert_sync (not alert): alert() queues on a daemon thread, which the interpreter would kill at exit
    # in a one-shot script like this -- the one message a day must actually leave before we return.
    sent = kwx_notify.alert_sync(text)
    print("telegram: sent" if sent else "telegram: TELEGRAM_* unset or send failed (digest above is the record)")


if __name__ == "__main__":
    main()
