#!/usr/bin/env python3
"""settle_recorder.py -- REUSABLE, STANDALONE settlement recorder for the paper sleeves.

WHY THIS EXISTS (sleeve audit, 2026-07-15)
------------------------------------------
Most paper sleeves log ENTRY-side metrics (CLV, pre-entry "edge", fair-value vs mid) but the
actual SETTLEMENT of each paper position -- the only thing that validates a sleeve on realized
money -- was never durably recorded for some of them. Concretely, on the gha-data branch:
  * kalshi-longshot / tailbias : entry log AND *_settled.csv both present  (settle works)
  * macro-paper                : macro_paper_<date>.jsonl + macro_pending.json present,
                                 macro_settled.jsonl  MISSING
  * kxwti-paper                : kxwti_paper_<date>.jsonl + kxwti_pending.json present,
                                 kxwti_settled.csv     MISSING

ROOT CAUSE (already documented in kalshi_longshot_paper.py's BUG-1 comment, but NOT retrofitted
into macro_paper.py / kxwti_paper.py): Kalshi's per-market `status` field for a RESOLVED market
is the string "finalized", NOT "settled". ("settled" is only a *query filter* value accepted by
GET /markets?status=settled; it never appears in a returned market object.) Both macro_paper.py
(line ~534) and kxwti_paper.py (line ~291) gate settlement on `status == "settled"`, so their
inline settle blocks never fire and their settled files are never created. kalshi_longshot_paper.py
and kalshi_tailbias_paper.py were fixed/written to check `status == "finalized"` and DO settle.

This utility fixes the problem WITHOUT touching the (fragile, entry-coupled) inline settle blocks:
it is a decoupled, resilient, idempotent recorder that reads a sleeve's durable entry log, asks
Kalshi for each market's actual result, computes realized P&L using THAT sleeve's exact contract
convention, and appends one row per settled position to a uniform <sleeve>_settled.jsonl ledger.
Because it keys resolution on `result in ("yes","no")` (which only populates once a market is
finalized) rather than on any particular status string, it is immune to the status-string trap.

WHAT IT DOES
------------
    python settle_recorder.py <entry_log_path> --sleeve <macro|kxwti|longshot|tailbias>
                              [--venue kalshi] [--out <path>] [--base <kalshi_api_base>]
                              [--max N] [--dry-run] [--verbose]

  1. Load the sleeve's entry log (JSON array pending-file OR .jsonl daily tape -- auto-detected).
  2. Filter to actual paper ENTRIES (see per-sleeve spec: e.g. kxwti only scores FILLED maker
     quotes; macro/longshot pending rows are all entries; macro daily-tape rows are entries only
     when would_trade_side is set).
  3. Skip any (ticker, entry_ts) already present in the out ledger  -> IDEMPOTENT (safe to run
     every workflow invocation; re-running never double-counts).
  4. For each remaining entry, GET /markets/{ticker}; if RESOLVED (result in yes/no), compute
     realized P&L per that sleeve's contract convention and append a settled row. Unresolved
     entries are left alone and retried on a later run.

READ-ONLY MARKET DATA ONLY. No auth, no orders, no money, no live-config edits. Public Kalshi
REST (GET /markets/{ticker}) exactly as fetch_kalshi.py / kalshi_longshot_paper.py already use it.

API ASSUMPTIONS (called out explicitly -- re-verify if Kalshi changes the API)
-----------------------------------------------------------------------------
  A1. A market is RESOLVED iff GET /markets/{ticker} -> market.result in ("yes","no"). We do NOT
      gate on the `status` string (that is the exact bug above). status is logged for visibility.
  A2. Binary payout convention: a YES contract pays $1 if result=="yes" else $0 (and symmetric
      for NO). All four sleeves are binary Kalshi markets, so settle_yes in {0.0, 1.0}.
  A3. Each sleeve's P&L formula and fee treatment MIRRORS that sleeve's own script EXACTLY, so
      this standalone ledger reproduces what the inline block would have written:
        - macro   : taker BUY of a binary at entry_price; pnl = win - entry_price - fee(entry_price),
                    win = 1 if result == side else 0; fee = quadratic taker fee ceil(.07*p(1-p)*100)/100.
        - kxwti   : maker quote, ZERO fee (matches kxwti_paper.py); side "bid" -> long YES ->
                    pnl = settle_yes - quote_price ; side "ask" -> short YES -> pnl = quote_price - settle_yes.
                    ONLY status=="filled" quotes are scored (resting/never-filled = no exposure).
        - longshot: maker SELL YES, ZERO maker fee; pnl = entry_sell_yes - settle_yes.
        - tailbias: BUY the favorite. settle_fav = 1 if result == fav_side else 0.
                    pnl_taker = settle_fav - taker_px - taker_fee_c/100 ; pnl_maker = settle_fav - maker_px.
                    "pnl" (the scored column) = pnl_taker (the pre-registered governing variant).
  A4. Idempotency key = (ticker, entry_ts). entry_ts is the sleeve's snapshot timestamp
      (macro/longshot: "ts"; kxwti: "snap_ts"; tailbias: "ts"). A market can appear in the entry
      log more than once across snapshots; each distinct (ticker, entry_ts) is one paper position.
  A5. Non-Kalshi venues are NOT implemented here (all four sleeves are Kalshi). A Polymarket
      adapter would resolve via gamma-api conditionId -> outcomePrices; stubbed with a clear error.

Every settled row carries "date" (settle date, UTC) and "pnl" keys, so the uniform ledger is
directly scoreable by `python edge_verdicts.py score <sleeve>_settled.jsonl` and re-auditable on
realized money with the same day-clustered t machinery used for FAVLONG.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.request
import datetime as dt

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


# ---------------------------------------------------------------------------------------------
# HTTP (stdlib only -- matches the no-pip style of macro/kxwti/longshot/tailbias)
# ---------------------------------------------------------------------------------------------
def eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)


def http_get_json(url, tries=4, timeout=20):
    hdrs = {"User-Agent": "research; settle_recorder.py (read-only)"}
    last = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except Exception as e:  # noqa: BLE001 -- deliberately broad; we retry+report
            last = e
            if a < tries - 1:
                time.sleep(1.2 * (a + 1))
    eprint(f"[settle_recorder] WARN: GET failed after {tries} tries: {url}: {last}")
    return None


def fetch_kalshi_result(base, ticker):
    """READ-ONLY. Returns (result, status) where result in {"yes","no",None}. Resolved iff
    result in ("yes","no")  (see API ASSUMPTION A1 -- do NOT gate on the status string)."""
    d = http_get_json(f"{base}/markets/{ticker}")
    m = (d or {}).get("market") or {}
    status = (m.get("status") or "").lower()
    result = (m.get("result") or "").lower()
    return (result if result in ("yes", "no") else None), status


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def quadratic_taker_fee(p, mult=0.07):
    """Kalshi standard quadratic taker fee, matches macro_paper.fee()."""
    if p is None or not (0.0 <= p <= 1.0):
        return 0.0
    return math.ceil(mult * p * (1.0 - p) * 100) / 100


# ---------------------------------------------------------------------------------------------
# entry-log loading (auto-detect JSON array pending-file vs .jsonl daily tape)
# ---------------------------------------------------------------------------------------------
def load_entry_records(path):
    """Yield raw dict records from either a JSON array (*_pending.json) or a .jsonl tape."""
    with open(path) as f:
        head = f.read()
    head_strip = head.lstrip()
    if head_strip.startswith("["):
        try:
            arr = json.loads(head)
        except Exception as e:  # noqa: BLE001
            eprint(f"[settle_recorder] ERROR: {path} looks like JSON but did not parse: {e}")
            return
        for r in (arr or []):
            if isinstance(r, dict):
                yield r
        return
    # JSONL tape
    for line in head.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict):
            yield r


# ---------------------------------------------------------------------------------------------
# per-sleeve specs: is_entry / entry_key / build settled row
# ---------------------------------------------------------------------------------------------
def _macro_is_entry(r):
    # pending.json rows are all real entries; daily-tape rows only when a side was triggered.
    if "would_trade_side" in r:
        return bool(r.get("would_trade_side")) and r.get("entry_price") is not None
    return bool(r.get("side")) and r.get("entry_price") is not None


def _macro_key(r):
    return r.get("ticker"), r.get("ts") or r.get("date")


def _macro_row(r, result, now_iso, now_date):
    side = (r.get("side") or r.get("would_trade_side") or "").lower()
    entry_price = fnum(r.get("entry_price"))
    if not side or entry_price is None:
        return None
    win = 1.0 if result == side else 0.0
    pnl = win - entry_price - quadratic_taker_fee(entry_price)
    return {
        "sleeve": "macro", "venue": "kalshi",
        "date": now_date, "settle_ts": now_iso,
        "entry_ts": r.get("ts") or r.get("date"),
        "ticker": r.get("ticker"), "series": r.get("series"), "rung": r.get("rung"),
        "side": side, "entry_price": round(entry_price, 4), "result": result,
        "pnl": round(pnl, 4),
    }


def _kxwti_is_entry(r):
    # only FILLED maker quotes carry real exposure and are scored.
    return (r.get("status") == "filled") and (r.get("quote_price") is not None) and bool(r.get("side"))


def _kxwti_key(r):
    return r.get("ticker"), r.get("snap_ts")


def _kxwti_row(r, result, now_iso, now_date):
    side = (r.get("side") or "").lower()   # "bid" (long YES) or "ask" (short YES)
    qp = fnum(r.get("quote_price"))
    if side not in ("bid", "ask") or qp is None:
        return None
    settle_yes = 1.0 if result == "yes" else 0.0
    pnl = (settle_yes - qp) if side == "bid" else (qp - settle_yes)   # ZERO fee (maker), matches kxwti_paper.py
    return {
        "sleeve": "kxwti", "venue": "kalshi",
        "date": now_date, "settle_ts": now_iso, "entry_ts": r.get("snap_ts"),
        "ticker": r.get("ticker"), "event_ticker": r.get("event_ticker"),
        "side": side, "quote_price": round(qp, 4),
        "fair_p_at_quote": r.get("fair_p_at_quote"), "edge_at_quote": r.get("edge_at_quote"),
        "result": result, "pnl": round(pnl, 4), "pnl_per_contract": round(pnl, 4),
    }


def _longshot_is_entry(r):
    return (r.get("entry_sell_yes") is not None) and bool(r.get("ticker"))


def _longshot_key(r):
    return r.get("ticker"), r.get("ts")


def _longshot_row(r, result, now_iso, now_date):
    esy = fnum(r.get("entry_sell_yes"))
    if esy is None:
        return None
    settle_yes = 1.0 if result == "yes" else 0.0
    pnl = esy - settle_yes     # maker SELL YES, zero maker fee
    return {
        "sleeve": "longshot", "venue": "kalshi",
        "date": now_date, "settle_ts": now_iso, "entry_ts": r.get("ts"),
        "ticker": r.get("ticker"), "category": r.get("category"),
        "entry_sell_yes": round(esy, 4), "result": result,
        "pnl": round(pnl, 4), "pnl_per_contract": round(pnl, 4),
    }


def _tailbias_is_entry(r):
    return bool(r.get("ticker")) and bool(r.get("fav_side")) and (r.get("taker_px") is not None)


def _tailbias_key(r):
    return r.get("ticker"), r.get("ts")


def _tailbias_row(r, result, now_iso, now_date):
    fav_side = (r.get("fav_side") or "").lower()
    taker_px = fnum(r.get("taker_px"))
    maker_px = fnum(r.get("maker_px"))
    taker_fee_c = fnum(r.get("taker_fee_c")) or 0.0
    if fav_side not in ("yes", "no") or taker_px is None:
        return None
    settle_fav = 1.0 if result == fav_side else 0.0
    pnl_taker = settle_fav - taker_px - taker_fee_c / 100.0
    pnl_maker = (settle_fav - maker_px) if maker_px is not None else None
    return {
        "sleeve": "tailbias", "venue": "kalshi",
        "date": now_date, "settle_ts": now_iso, "entry_ts": r.get("ts"),
        "ticker": r.get("ticker"), "asset": r.get("asset"),
        "ws": r.get("ws"), "we": r.get("we"),
        "tail_side": r.get("tail_side"), "tail_px": r.get("tail_px"),
        "fav_side": fav_side, "taker_px": round(taker_px, 4),
        "maker_px": round(maker_px, 4) if maker_px is not None else None,
        "result": result, "settle_fav": settle_fav,
        "pnl_taker": round(pnl_taker, 4),
        "pnl_maker": round(pnl_maker, 4) if pnl_maker is not None else None,
        "pnl": round(pnl_taker, 4),     # scored column = the pre-registered governing (taker) variant
    }


SLEEVES = {
    "macro":    {"is_entry": _macro_is_entry,    "key": _macro_key,    "row": _macro_row},
    "kxwti":    {"is_entry": _kxwti_is_entry,    "key": _kxwti_key,    "row": _kxwti_row},
    "longshot": {"is_entry": _longshot_is_entry, "key": _longshot_key, "row": _longshot_row},
    "tailbias": {"is_entry": _tailbias_is_entry, "key": _tailbias_key, "row": _tailbias_row},
}


def load_existing_keys(out_path):
    """Set of (ticker, entry_ts) already recorded -> idempotency."""
    keys = set()
    if not os.path.exists(out_path):
        return keys
    with open(out_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            keys.add((d.get("ticker"), d.get("entry_ts")))
    return keys


def run(entry_log, sleeve, venue="kalshi", out_path=None, base=KALSHI_BASE,
        max_lookups=None, dry_run=False, verbose=False):
    if sleeve not in SLEEVES:
        raise SystemExit(f"unknown sleeve '{sleeve}' (choose from {sorted(SLEEVES)})")
    if venue != "kalshi":
        raise SystemExit(f"venue '{venue}' not implemented (see API ASSUMPTION A5; only kalshi). "
                         f"Read-only market data only; no orders.")
    if not os.path.exists(entry_log):
        raise SystemExit(f"entry log not found: {entry_log}")
    spec = SLEEVES[sleeve]
    out_path = out_path or os.path.join(os.path.dirname(os.path.abspath(entry_log)),
                                        f"{sleeve}_settled.jsonl")

    now = dt.datetime.now(dt.timezone.utc)
    now_iso = now.isoformat(timespec="seconds")
    now_date = now.date().isoformat()

    already = load_existing_keys(out_path)
    # de-dup entries within the log itself by key (a ticker can recur across daily-tape lines)
    entries = {}
    for r in load_entry_records(entry_log):
        if not spec["is_entry"](r):
            continue
        k = spec["key"](r)
        if k[0] is None:
            continue
        entries.setdefault(k, r)      # first occurrence of each (ticker, entry_ts) wins

    to_check = [(k, r) for k, r in entries.items() if k not in already]
    if verbose:
        eprint(f"[settle_recorder] {sleeve}: {len(entries)} distinct entries, "
               f"{len(already)} already settled, {len(to_check)} to check")

    result_cache = {}
    new_rows, n_resolved, n_unresolved, n_looked = [], 0, 0, 0
    for k, r in to_check:
        if max_lookups is not None and n_looked >= max_lookups:
            break
        ticker = k[0]
        if ticker not in result_cache:
            result_cache[ticker] = fetch_kalshi_result(base, ticker)
            n_looked += 1
        result, status = result_cache[ticker]
        if result is None:
            n_unresolved += 1
            if verbose:
                eprint(f"    unresolved: {ticker} (status={status or 'n/a'})")
            continue
        row = spec["row"](r, result, now_iso, now_date)
        if row is None:
            continue
        row["market_status"] = status
        new_rows.append(row)
        n_resolved += 1

    if dry_run:
        for row in new_rows:
            print(json.dumps(row))
        eprint(f"[settle_recorder] DRY-RUN {sleeve}: would append {len(new_rows)} settled row(s) "
               f"to {out_path} | resolved {n_resolved} unresolved {n_unresolved}")
        return new_rows

    if new_rows:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "a") as f:
            for row in new_rows:
                f.write(json.dumps(row, default=str) + "\n")

    print(f"[{now_iso}] settle_recorder {sleeve}: appended {len(new_rows)} settled row(s) to "
          f"{out_path} | resolved {n_resolved} | still-unresolved {n_unresolved} | "
          f"already-recorded {len(already)}")
    return new_rows


def main():
    ap = argparse.ArgumentParser(description="Reusable, read-only settlement recorder for paper sleeves.")
    ap.add_argument("entry_log", help="path to the sleeve's entry log (*_pending.json or *_<date>.jsonl)")
    ap.add_argument("--sleeve", required=True, choices=sorted(SLEEVES), help="which sleeve's schema/P&L to use")
    ap.add_argument("--venue", default="kalshi", help="market venue (only 'kalshi' implemented)")
    ap.add_argument("--out", default=None, help="output ledger path (default: <entry_dir>/<sleeve>_settled.jsonl)")
    ap.add_argument("--base", default=KALSHI_BASE, help="Kalshi REST base URL")
    ap.add_argument("--max", type=int, default=None, dest="max_lookups", help="cap number of market lookups this run")
    ap.add_argument("--dry-run", action="store_true", help="print rows, do not write the ledger")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    run(a.entry_log, a.sleeve, venue=a.venue, out_path=a.out, base=a.base,
        max_lookups=a.max_lookups, dry_run=a.dry_run, verbose=a.verbose)


if __name__ == "__main__":
    main()
