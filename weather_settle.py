#!/usr/bin/env python3
"""weather_settle.py -- the settlement-join "second pass" spec'd (but never implemented) in
weather_clv_harness.py's docstring.

WHAT IT DOES
  For every (event,bracket) row in the snapshot log whose Kalshi market has by now CLOSED and
  FINALIZED, fetch the settlement result and back-fill `actual_high` / `settled` on ALL rows of
  that (event,bracket) -- however many times it was snapshotted before close -- then append
  per-row CLV/paper-P&L columns. Rows for markets not yet finalized are left untouched (blank),
  same as today; re-running is idempotent (only blanks get filled; already-filled rows are
  skipped unless --refresh).

SETTLEMENT SOURCE
  Primary: Kalshi public REST `GET /markets?event_ticker=...` (no auth needed -- verified live).
  For a finalized market this already returns BOTH the per-bracket outcome (`result`: "yes"/"no")
  AND the value Kalshi used to settle it (`expiration_value`, the actual observed high, e.g.
  "76.00") in a single call -- no NWS CLI scrape needed for the common case. One call per event
  covers every bracket in that event (Kalshi weather events have ~5-6 brackets).
    Verified live 2026-07-12: `KXHIGHNY-26JUN20` -> status=finalized, result=no/yes per bracket,
    expiration_value=81.00. Markets ~24-48h past their target date are consistently finalized;
    markets from the prior day (e.g. still 26JUL11 vs run-date 26JUL12) can still show
    status=active -- settlement lags the observed day by roughly a day, per Kalshi's own rule
    ("sooner of 7-8am ET following the data release, or one week after").
  Fallback: NWS `api.weather.gov/stations/{station}/observations` max hourly temp for the local
  day, used ONLY if an event is more than FALLBACK_DAYS past its target date and Kalshi still
  hasn't finalized it (stale/API hiccup). Best-effort: a quick live check found this endpoint
  returns 0 observations for at least one of our stations (KNYC) over a same-window query --
  station-id / archive-depth quirks on NWS's side -- so treat it as a safety net, not primary.

CLV / PAPER P&L RULE (matches the BUY rule edge_verdicts.py's weather loader already documents)
  Each row IS one bracket's YES side. Entry = k_yes_ask at snapshot time (this collector never
  logs re-quotes between snapshots, so "entry" = the ask observed at that snapshot; "exit" =
  settlement, not an intermediate close -- CLV here means snapshot-time-edge-vs-final-truth, not
  book-close CLV, since we don't separately log a pre-settlement closing book).
    entry_prob = k_yes_ask / 100        (ask is logged in cents)
    fee        = 0.07 * entry_prob * (1 - entry_prob)     (Kalshi quadratic taker fee, in $/contract)
    edge       = nbm_p - entry_prob     (NBM fair prob of this bracket minus what you'd pay)
    signal     = edge > fee             (would the documented BUY rule fire on this row?)
    outcome    = 1.0 if settled(result)=="yes" else 0.0
    pnl        = outcome - entry_prob - fee     (paper P&L per contract if bought, $, always
                 computed once settled so descriptive stats aren't signal-gated; edge_verdicts.py
                 additionally gates by `signal` when it scores the BUY-rule verdict)

OUTPUT
  Rewrites the log file IN PLACE (same path passed in): back-fills actual_high/settled on
  matched historical rows and appends the pnl/signal columns (entry_prob,fee,edge,signal,
  outcome,pnl) to every row (blank where not yet computable). This is the file
  gha_data/weather/weather_clv_log.csv already committed by kalshi-weather.yml -- filling it in
  place means the EXISTING workflow (unchanged) naturally ships the join: no edit to
  kalshi-weather.yml needed. edge_verdicts.py's weather loader reads this same path/schema and
  needs no format change (it looks up columns by name when a header is present).

USAGE
  python weather_settle.py <log_csv> [--grace-hours 20] [--fallback-days 4] [--refresh] [--dry-run]

Called automatically by weather_clv_harness.py after each snapshot append (best-effort, never
fails the collector run) -- see its __main__.
"""
from __future__ import annotations

import csv
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

H = {"User-Agent": "kalshi-weather-research dgkenn@bu.edu"}
KBASE = "https://api.elections.kalshi.com/trade-api/v2"

HEADER = ["ts", "city", "station", "event", "bracket", "lo", "hi", "nbm_high",
          "nbm_sigma", "nbm_p", "k_yes_bid", "k_yes_ask", "k_mid", "actual_high",
          "settled", "nbm_cycle", "entry_prob", "fee", "edge", "signal", "outcome", "pnl"]
N_BASE = 16  # original harness columns (ts .. nbm_cycle)
IDX = {c: i for i, c in enumerate(HEADER)}

FEE = lambda p: 0.07 * p * (1 - p)

_EVDATE_RE = re.compile(r"-(\d{2}[A-Z]{3}\d{2})$")


def event_target_date(event: str):
    m = _EVDATE_RE.search(event)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%y%b%d").replace(tzinfo=timezone.utc).date()
    except ValueError:
        return None


def read_rows(path):
    """Read the log tolerantly whether or not it currently has a header row."""
    with open(path, newline="") as f:
        raw = list(csv.reader(f))
    if raw and raw[0][:1] == ["ts"]:
        rows = raw[1:]
    else:
        rows = raw
    out = []
    for r in rows:
        r = list(r) + [""] * (len(HEADER) - len(r))  # pad to full (possibly extended) width
        out.append(r[:len(HEADER)])
    return out


def write_rows(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    os.replace(tmp, path)


def fetch_event_settlement(event: str, session: requests.Session, retries: int = 3):
    """-> dict[bracket_subtitle] = (status, result, expiration_value_str) or {} on failure/no data.
    Retries on transient network/proxy errors (observed: sporadic empty results on a clean
    re-run of the same request a few minutes apart) so a settle pass gives a stable, repeatable
    row count rather than however many requests happened to survive the network that run."""
    last_exc = None
    for attempt in range(retries):
        try:
            r = session.get(KBASE + "/markets", params={"event_ticker": event, "limit": 100},
                             headers=H, timeout=30)
            if r.status_code == 200:
                ms = r.json().get("markets", [])
                out = {}
                for m in ms:
                    sub = m.get("subtitle") or m.get("yes_sub_title") or ""
                    out[sub] = (m.get("status"), m.get("result"), m.get("expiration_value"))
                return out
            last_exc = f"HTTP {r.status_code}"
        except Exception as e:
            last_exc = e
        time.sleep(0.5 * (attempt + 1))
    eprint(f"[weather_settle] giving up on {event} after {retries} attempts: {last_exc}")
    return {}


def eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)


def nws_fallback_high(station: str, target_date, session: requests.Session):
    """Best-effort NWS observed max temp (F) for the local day. Returns int or None.
    Used only when Kalshi hasn't finalized an event well past its target date."""
    try:
        start = datetime(target_date.year, target_date.month, target_date.day, 5, tzinfo=timezone.utc)
        end = start + timedelta(hours=30)
        r = session.get(f"https://api.weather.gov/stations/{station}/observations",
                         params={"start": start.isoformat(), "end": end.isoformat(), "limit": 200},
                         headers=H, timeout=20)
        if r.status_code != 200:
            return None
        feats = r.json().get("features", [])
        temps_c = [f["properties"]["temperature"]["value"] for f in feats
                   if f.get("properties", {}).get("temperature", {}).get("value") is not None]
        if not temps_c:
            return None
        return round(max(temps_c) * 9 / 5 + 32)
    except Exception:
        return None


def settle_log(path: str, grace_hours: float = 20.0, fallback_days: int = 4,
                refresh: bool = False, dry_run: bool = False, verbose: bool = True):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        if verbose:
            print(f"[weather_settle] {path} missing/empty, nothing to settle")
        return dict(n_rows=0, n_events_checked=0, n_rows_filled=0)

    rows = read_rows(path)
    now = datetime.now(timezone.utc)

    # which rows need work
    need_event = {}
    for i, r in enumerate(rows):
        if not refresh and r[IDX["settled"]].strip() and r[IDX["actual_high"]].strip():
            continue
        ev = r[IDX["event"]]
        tgt = event_target_date(ev)
        if tgt is None:
            continue
        # don't even bother calling the API until the event's local day is clearly over
        if now < datetime(tgt.year, tgt.month, tgt.day, tzinfo=timezone.utc) + timedelta(hours=grace_hours):
            continue
        need_event.setdefault(ev, []).append(i)

    session = requests.Session()
    n_events_checked = 0
    n_rows_filled = 0
    cache = {}
    for ev, idxs in need_event.items():
        n_events_checked += 1
        settle_map = fetch_event_settlement(ev, session)
        cache[ev] = settle_map
        time.sleep(0.08)
        if not settle_map:
            continue
        finalized = all(st == "finalized" for st, _, _ in settle_map.values())
        tgt = event_target_date(ev)
        actual_val = None
        for st, res, exp_val in settle_map.values():
            if st == "finalized" and exp_val not in (None, ""):
                try:
                    actual_val = int(round(float(exp_val)))
                except (TypeError, ValueError):
                    pass
                break

        if not finalized and tgt is not None and (now.date() - tgt).days >= fallback_days:
            # stale -- try NWS observed as a fallback actual, and infer bracket result from bounds
            for i in idxs:
                r = rows[i]
                if actual_val is None:
                    actual_val = nws_fallback_high(r[IDX["station"]], tgt, session)
                    time.sleep(0.05)
                if actual_val is None:
                    continue
                lo = r[IDX["lo"]].strip()
                hi = r[IDX["hi"]].strip()
                lo_v = int(lo) if lo else None
                hi_v = int(hi) if hi else None
                inb = (lo_v is None or actual_val >= lo_v) and (hi_v is None or actual_val <= hi_v)
                r[IDX["actual_high"]] = str(actual_val)
                r[IDX["settled"]] = "yes" if inb else "no"
                n_rows_filled += 1
            continue

        if not finalized:
            continue  # not settled yet, still within normal window -- try again next run

        for i in idxs:
            r = rows[i]
            sub = r[IDX["bracket"]]
            hit = settle_map.get(sub)
            if hit is None:
                continue
            st, res, exp_val = hit
            if st != "finalized" or res not in ("yes", "no"):
                continue
            r[IDX["settled"]] = res
            if actual_val is not None:
                r[IDX["actual_high"]] = str(actual_val)
            elif exp_val not in (None, ""):
                try:
                    r[IDX["actual_high"]] = str(int(round(float(exp_val))))
                except (TypeError, ValueError):
                    pass
            n_rows_filled += 1

    # compute pnl columns for every row that now has both actual_high+settled and a valid ask
    n_scored = 0
    for r in rows:
        if not (r[IDX["settled"]].strip() and r[IDX["actual_high"]].strip()):
            continue
        ask_s = r[IDX["k_yes_ask"]].strip()
        p_s = r[IDX["nbm_p"]].strip()
        if not ask_s or not p_s:
            continue
        try:
            ask = float(ask_s) / 100.0
            p = float(p_s)
        except ValueError:
            continue
        fee = FEE(ask)
        edge = p - ask
        signal = edge > fee
        outcome = 1.0 if r[IDX["settled"]].strip().lower() == "yes" else 0.0
        pnl = outcome - ask - fee
        r[IDX["entry_prob"]] = f"{ask:.4f}"
        r[IDX["fee"]] = f"{fee:.4f}"
        r[IDX["edge"]] = f"{edge:.4f}"
        r[IDX["signal"]] = "1" if signal else "0"
        r[IDX["outcome"]] = f"{outcome:.0f}"
        r[IDX["pnl"]] = f"{pnl:.4f}"
        n_scored += 1

    if not dry_run:
        write_rows(path, rows)

    stats = dict(n_rows=len(rows), n_events_checked=n_events_checked,
                 n_rows_filled=n_rows_filled, n_rows_scoreable=n_scored)
    if verbose:
        print(f"[weather_settle] {path}: {len(rows)} rows, checked {n_events_checked} events, "
              f"newly filled {n_rows_filled} rows, {n_scored} rows now scoreable "
              f"(dry_run={dry_run})")
    return stats


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--grace-hours", type=float, default=20.0)
    ap.add_argument("--fallback-days", type=int, default=4)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    settle_log(args.path, grace_hours=args.grace_hours, fallback_days=args.fallback_days,
               refresh=args.refresh, dry_run=args.dry_run)
