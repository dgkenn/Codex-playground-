"""sleeve_ledger.py -- unified daily P&L ledger across every trading sleeve in this repo.

One normalizer per sleeve, all emitting the same row shape so portfolio_allocator.py (and
dashboard.py's Portfolio section) can consume them without caring about each sleeve's native
file format:

    {"date": "YYYY-MM-DD", "sleeve": <str>, "pnl_usd": <float>, "notional_usd": <float>,
     "n_trades": <int>, "is_live": <bool>}

Sleeves covered (per the multi-market/multi-strategy roadmap):
  - crypto_mm_<asset>  LIVE  -- the maker-box harvester (kalshi_trader.py). Two possible sources,
    read best-effort and merged de-duped on (asset, window-start):
      1. gha_data/live_recon_<asset><tenor>m_r*.jsonl (NEW schema: kalshi_trader.py's
         `_recon_write`, one row per settled window with `net`/`gross` already in dollars).
      2. live_state/<date>/kalshi_winrec_<asset>15m.jsonl (older per-window audit record,
         `realized` field) -- read from a local `live_state/` checkout if present, else a
         best-effort `git show` against `origin/live-state` (mirrors live_gate.py's pattern),
         else skipped entirely. Source 1 wins on overlap since its schema is the one meant to
         become authoritative.
  - longshot_paper    PAPER -- kalshi_longshot_paper.py's gha_data/longshot/longshot_settled.csv
    (also checks gha_data/longshot_settled.csv, the argv-less default). Empty/absent -> 0 rows,
    not an error: this sleeve is genuinely pre-settlement most of the time (45-day max life).
  - wti_paper         PAPER -- kxwti_paper.py's gha_data/kxwti_settled.csv.
  - macro_paper       PAPER -- macro_paper.py's gha_data/macro_settled.jsonl (grouped by the
    `series` field -- CPI vs Fed-decision -- when present, else lumped as "macro_paper").

Every loader is wrapped so a missing/malformed/immature source degrades to zero rows instead of
raising -- this must run clean on a bot that's mid-bootstrap on every sleeve at once.

    python3 sleeve_ledger.py               # per-sleeve daily table + totals
    python3 sleeve_ledger.py --days 14     # narrower trailing window
"""
from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

from dataio import jl_glob, jl_lines

Row = dict


def _utc_date(ts: float) -> str:
    return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%d")


def _f(x, default=0.0):
    try:
        v = float(x)
        return v if v == v else default   # NaN guard
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------------------------
# crypto_mm_<asset>  (LIVE)
# --------------------------------------------------------------------------------------------

def _live_recon_rows() -> list[dict]:
    """gha_data/live_recon_<asset><tenor>m_r*.jsonl -- new schema, dollars already in net/gross."""
    out = []
    for fp in jl_glob("gha_data/live_recon_*.jsonl"):
        for r in jl_lines(fp):
            if r.get("ws") is None or r.get("asset") is None:
                continue
            out.append(r)
    return out


def _live_state_winrec_rows() -> list[dict]:
    """kalshi_winrec_<asset>15m.jsonl -- local live_state/ checkout first, else best-effort git
    plumbing against origin/live-state (never raises; returns [] if the branch isn't fetched)."""
    local = sorted(glob.glob("live_state/*/kalshi_winrec_*.jsonl")) + \
        sorted(glob.glob("live_state/kalshi_winrec_*.jsonl"))
    if local:
        out = []
        for fp in local:
            with open(fp) as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        out.append(json.loads(ln))
                    except Exception:
                        continue
        return out
    # no local checkout -- try reading straight out of the fetched-but-not-checked-out branch ref
    try:
        ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/live-state"],
                             capture_output=True, text=True, timeout=15)
        if ls.returncode != 0:
            return []
        paths = [p for p in ls.stdout.splitlines() if "kalshi_winrec_" in p and p.endswith(".jsonl")]
        out = []
        for p in paths:
            show = subprocess.run(["git", "show", f"origin/live-state:{p}"],
                                   capture_output=True, text=True, timeout=15)
            if show.returncode != 0:
                continue
            for ln in show.stdout.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    continue
        return out
    except Exception:
        return []


def load_crypto_mm() -> list[Row]:
    buckets: dict[tuple, dict] = defaultdict(lambda: {"pnl": 0.0, "notional": 0.0, "n": 0})
    seen_windows: set = set()

    try:
        for r in _live_recon_rows():
            asset, ws = r.get("asset"), r.get("ws")
            key = (asset, ws)
            seen_windows.add(key)
            d = _utc_date(ws)
            b = buckets[(d, asset)]
            b["pnl"] += _f(r.get("net"))
            b["notional"] += abs(_f(r.get("inv_max"))) or abs(_f(r.get("gross")))
            b["n"] += int(r.get("fills") or 0)
    except Exception:
        pass

    try:
        for r in _live_state_winrec_rows():
            asset, ws = r.get("asset"), r.get("ws")
            if asset is None or ws is None:
                continue
            key = (asset, ws)
            if key in seen_windows:      # live_recon already covers this window -- don't double-count
                continue
            seen_windows.add(key)
            d = _utc_date(ws)
            b = buckets[(d, asset)]
            b["pnl"] += _f(r.get("realized"))
            b["notional"] += _f(r.get("cost_yes")) + _f(r.get("cost_no"))
            b["n"] += int(r.get("n_taker") or 0) + int(r.get("n_maker") or 0)
    except Exception:
        pass

    rows = []
    for (d, asset), b in sorted(buckets.items()):
        rows.append({"date": d, "sleeve": f"crypto_mm_{asset}", "pnl_usd": round(b["pnl"], 4),
                     "notional_usd": round(b["notional"], 4), "n_trades": b["n"], "is_live": True})
    return rows


# --------------------------------------------------------------------------------------------
# longshot_paper  (PAPER)
# --------------------------------------------------------------------------------------------

def _read_csv_rows(*candidate_paths) -> list[dict]:
    for path in candidate_paths:
        if os.path.exists(path):
            try:
                with open(path, newline="") as fh:
                    return list(csv.DictReader(fh))
            except Exception:
                continue
    return []


def load_longshot_paper() -> list[Row]:
    rows = _read_csv_rows("gha_data/longshot/longshot_settled.csv", "gha_data/longshot_settled.csv")
    buckets: dict[str, dict] = defaultdict(lambda: {"pnl": 0.0, "notional": 0.0, "n": 0})
    for r in rows:
        try:
            ts = r.get("settle_ts") or r.get("snap_ts")
            d = ts[:10] if ts else None
            pnl = float(r["pnl_per_contract"])
            entry = float(r.get("entry_sell_yes", 0.0))
        except (KeyError, ValueError, TypeError):
            continue
        if not d:
            continue
        # short-YES longshot: premium collected = entry_sell_yes, capital at risk (max loss) =
        # 1 - entry_sell_yes (worst case the YES side pays out $1) -- that's the honest notional.
        b = buckets[d]
        b["pnl"] += pnl
        b["notional"] += max(1.0 - entry, 0.0)
        b["n"] += 1
    out = [{"date": d, "sleeve": "longshot_paper", "pnl_usd": round(b["pnl"], 4),
            "notional_usd": round(b["notional"], 4), "n_trades": b["n"], "is_live": False}
           for d, b in sorted(buckets.items())]
    return out


# --------------------------------------------------------------------------------------------
# wti_paper  (PAPER)
# --------------------------------------------------------------------------------------------

def load_wti_paper() -> list[Row]:
    rows = _read_csv_rows("gha_data/kxwti_settled.csv")
    buckets: dict[str, dict] = defaultdict(lambda: {"pnl": 0.0, "notional": 0.0, "n": 0})
    for r in rows:
        try:
            ts = r.get("settle_ts") or r.get("snap_ts")
            d = ts[:10] if ts else None
            pnl = float(r["pnl_per_contract"])
            price = float(r.get("quote_price", 0.0))
            side = (r.get("side") or "").lower()
        except (KeyError, ValueError, TypeError):
            continue
        if not d:
            continue
        # bid side = long YES at quote_price (capital at risk = quote_price); ask side = short
        # YES at quote_price (capital at risk = 1 - quote_price, worst case YES settles).
        notional = price if side == "bid" else max(1.0 - price, 0.0)
        b = buckets[d]
        b["pnl"] += pnl
        b["notional"] += notional
        b["n"] += 1
    out = [{"date": d, "sleeve": "wti_paper", "pnl_usd": round(b["pnl"], 4),
            "notional_usd": round(b["notional"], 4), "n_trades": b["n"], "is_live": False}
           for d, b in sorted(buckets.items())]
    return out


# --------------------------------------------------------------------------------------------
# macro_paper (CPI / Fed)  (PAPER)
# --------------------------------------------------------------------------------------------

def load_macro_paper() -> list[Row]:
    path = "gha_data/macro_settled.jsonl"
    buckets: dict[tuple, dict] = defaultdict(lambda: {"pnl": 0.0, "notional": 0.0, "n": 0})
    if os.path.exists(path):
        try:
            with open(path) as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        r = json.loads(ln)
                    except Exception:
                        continue
                    d = r.get("date") or (r.get("settle_ts") or "")[:10]
                    if not d:
                        continue
                    series = r.get("series") or "macro"
                    sleeve = f"macro_paper_{series}"
                    b = buckets[(d, sleeve)]
                    b["pnl"] += _f(r.get("pnl"))
                    # entry_price IS the $ cost/capital-at-risk per contract regardless of side
                    # (macro_paper.py's mk_row sets it to `ya` for YES, `1-yb` for NO).
                    b["notional"] += _f(r.get("entry_price"))
                    b["n"] += 1
        except Exception:
            pass
    out = [{"date": d, "sleeve": sleeve, "pnl_usd": round(b["pnl"], 4),
            "notional_usd": round(b["notional"], 4), "n_trades": b["n"], "is_live": False}
           for (d, sleeve), b in sorted(buckets.items())]
    return out


# --------------------------------------------------------------------------------------------
# aggregate API
# --------------------------------------------------------------------------------------------

def load_all() -> list[Row]:
    """Every sleeve, each independently guarded -- one loader raising never blocks the rest."""
    rows: list[Row] = []
    for loader in (load_crypto_mm, load_longshot_paper, load_wti_paper, load_macro_paper):
        try:
            rows.extend(loader())
        except Exception:
            pass
    return rows


def by_sleeve(rows: list[Row]) -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        out[r["sleeve"]].append(r)
    for k in out:
        out[k].sort(key=lambda r: r["date"])
    return dict(out)


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------

def _print_table(rows: list[Row], days: int | None) -> None:
    sleeves = by_sleeve(rows)
    if not sleeves:
        print("no sleeve data found (all sources absent/immature -- this is expected cold-start).")
        return
    for name in sorted(sleeves):
        srows = sleeves[name]
        if days:
            cutoff = sorted({r["date"] for r in srows})[-days:]
            srows = [r for r in srows if r["date"] in cutoff]
        if not srows:
            continue
        live_tag = "LIVE" if srows[0]["is_live"] else "PAPER"
        print(f"\n== {name} [{live_tag}] ==")
        print(f"{'date':<12}{'pnl_usd':>12}{'notional_usd':>14}{'n_trades':>10}")
        tot_pnl = tot_notional = tot_n = 0
        for r in srows:
            print(f"{r['date']:<12}{r['pnl_usd']:>12.4f}{r['notional_usd']:>14.4f}{r['n_trades']:>10}")
            tot_pnl += r["pnl_usd"]; tot_notional += r["notional_usd"]; tot_n += r["n_trades"]
        n_days = len(srows)
        print(f"{'TOTAL':<12}{tot_pnl:>12.4f}{tot_notional:>14.4f}{tot_n:>10}   "
              f"({n_days} day(s), mean/day={tot_pnl / n_days:+.4f})")

    print("\n== grand totals (all sleeves) ==")
    all_rows = [r for rs in sleeves.values() for r in rs]
    tot_pnl = sum(r["pnl_usd"] for r in all_rows)
    tot_notional = sum(r["notional_usd"] for r in all_rows)
    tot_n = sum(r["n_trades"] for r in all_rows)
    n_live_sleeves = sum(1 for rs in sleeves.values() if rs and rs[0]["is_live"])
    print(f"sleeves: {len(sleeves)} ({n_live_sleeves} live) | rows: {len(all_rows)} | "
          f"total pnl_usd={tot_pnl:+.4f} | total notional_usd={tot_notional:.4f} | "
          f"total n_trades={tot_n}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, default=None, help="trailing days per sleeve (default: all)")
    args = ap.parse_args()
    rows = load_all()
    _print_table(rows, args.days)


if __name__ == "__main__":
    main()
