#!/usr/bin/env python3
"""edge_verdicts.py -- generic forward-bar scorer for dormant paper-tracked edge streams.

PRE-REGISTERED BAR (same one used for the MM variants elsewhere in this repo):
  >= 14 forward days of data, day-clustered t >= 3 vs a null (default null = 0), and
  positive on >= 80% of days (day-mean P&L > null on >= 80% of the days observed).

Day-clustering matters because rows within a day are correlated (shared regime/volatility/
liquidity), so treating every row as an independent observation overstates significance.
We therefore always collapse to ONE mean-P&L-per-day observation before computing t.

Works generically against any dated P&L rows. Ships parsers for the THREE dormant streams
actually found on gha-data (see per-stream notes below); `--kind auto` sniffs the file.

  kalshi-longshot   gha_data/longshot/longshot_settled.csv   (csv, header written by
                    kalshi_longshot_paper.py: settle_ts,snap_ts,ticker,category,
                    entry_sell_yes,result,pnl_per_contract,vol_after_entry)
                    date = settle_ts, value = pnl_per_contract.
                    STATUS (checked 2026-07-11 against a shallow fetch of gha-data): this
                    file DOES NOT EXIST YET -- 0 rows. kalshi-longshot.yml IS an active
                    workflow (.github/workflows/kalshi-longshot.yml, not just the .sample),
                    and longshot_pending.json has 635 open paper positions since
                    2026-06-18, but essentially all of them have far-future close_time
                    (Politics/Entertainment/SciTech longshots resolving in weeks-months);
                    only one had a close_time in the past as of the fetch, and it had not
                    yet posted a settle row. NOT a collector bug -- the collector is
                    correctly SETTLING matured pendings each run, there just aren't any
                    matured pendings yet. Not scoreable until settlements accrue.

  kalshi-weather    gha_data/weather/weather_clv_log.csv   (csv, header written by
                    weather_clv_harness.py: ts,city,station,event,bracket,lo,hi,nbm_high,
                    nbm_sigma,nbm_p,k_yes_bid,k_yes_ask,k_mid,actual_high,settled,nbm_cycle)
                    date = ts, value would be a CLV/PnL rule over (nbm_p, k_yes_ask, outcome).
                    STATUS (checked against 1295 data rows spanning 2026-06-15..07-12): the
                    `actual_high` and `settled` columns are ALWAYS BLANK -- the harness's own
                    docstring describes a "second pass" that joins the NWS CLI settlement and
                    computes PnL/Brier, but that second pass is never invoked anywhere in this
                    repo (grepped for writers of those two columns: none). So this stream logs
                    snapshots (NBM-implied prob vs Kalshi book) but NO row is ever P&L-scoreable
                    as shipped. ONE-LINE-ISH FIX the collector would need (NOT made here, per
                    instructions): after an event's close_time has passed, look up the NWS CLI
                    (or Kalshi settled-market result) for that station/date and rewrite matching
                    rows' `actual_high`/`settled` fields -- i.e. actually wire up the settlement
                    join that the docstring already spec'd but the code never implements.

  xvenue            gha_data/xvenue_<date>.jsonl (see cross_venue_gap.py)
                    date = day, value = pnl_gross_c (cents/contract).
                    STATUS: cross_venue_gap.py's incremental mode (b) is intentionally
                    DISABLED -- see XVENUE_FINDINGS.md -- because Kalshi btc15m and Polymarket
                    btc-updown-5m are different-tenor markets (not the same event), so a
                    forward "edge" track would misrepresent directional exposure as arbitrage.
                    No xvenue_<date>.jsonl files exist. Generic parser support is still wired
                    here (in case that decision is revisited) and can also score the
                    HISTORICAL scan rows for descriptive/diagnostic purposes via `--kind xvenue-scan`.

Usage:
  python edge_verdicts.py score <path> [--kind auto|longshot|weather|xvenue|generic]
                                        [--date-col C] [--value-col C] [--null 0.0]
  python edge_verdicts.py auto [--data-dir gha_data]     # discover + score all 3 known streams
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, date


def eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)


# --------------------------------------------------------------------------------------
# date parsing helper
# --------------------------------------------------------------------------------------
def to_date(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.utcfromtimestamp(float(v)).date()
        except Exception:
            return None
    s = str(v).strip()
    if not s:
        return None
    s2 = s.replace("Z", "+00:00")
    for parser in (
        lambda x: datetime.fromisoformat(x).date(),
        lambda x: datetime.strptime(x[:10], "%Y-%m-%d").date(),
    ):
        try:
            return parser(s2)
        except Exception:
            continue
    try:
        return datetime.utcfromtimestamp(float(s)).date()
    except Exception:
        return None


# --------------------------------------------------------------------------------------
# per-stream loaders -> list of (date, value)
# --------------------------------------------------------------------------------------
def load_longshot(path: str):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            d = to_date(r.get("settle_ts") or r.get("snap_ts"))
            try:
                v = float(r.get("pnl_per_contract"))
            except (TypeError, ValueError):
                continue
            if d is None:
                continue
            rows.append((d, v))
    return rows


def load_weather_clv(path: str):
    """Only rows with a non-blank `settled`/`actual_high` are scoreable. Applies the rule
    documented in weather_clv_harness.py: BUY the bracket when nbm_p - yes_ask clears the
    per-contract taker fee (0.07*p*(1-p)); pnl = outcome - entry - fee (skip if no signal)."""
    rows = []
    if not os.path.exists(path):
        return rows, 0
    FEE = lambda p: 0.07 * p * (1 - p)
    n_total = 0
    with open(path, newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        cols = header if header and "ts" in header else None
        idx = {c: i for i, c in enumerate(cols)} if cols else {
            "ts": 0, "actual_high": 13, "settled": 14, "nbm_p": 9, "k_yes_ask": 11,
        }
        for r in rdr:
            n_total += 1
            if len(r) <= max(idx.values()):
                continue
            settled = (r[idx["settled"]] or "").strip()
            actual_high = (r[idx["actual_high"]] or "").strip()
            if not settled or not actual_high:
                continue  # unscoreable snapshot row (the common case, as shipped)
            d = to_date(r[idx["ts"]])
            try:
                nbm_p = float(r[idx["nbm_p"]])
                ask = float(r[idx["k_yes_ask"]])
            except (ValueError, IndexError):
                continue
            outcome = 1.0 if settled.lower() in ("1", "true", "yes", "y") else 0.0
            if nbm_p - ask <= FEE(ask):
                continue  # no buy signal that day
            pnl = outcome - ask - FEE(ask)
            if d is not None:
                rows.append((d, pnl))
    return rows, n_total


def load_xvenue_jsonl(paths):
    rows = []
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                dd = to_date(d.get("day") or d.get("date") or d.get("t") or d.get("ts"))
                v = d.get("pnl_gross_c", d.get("pnl", d.get("value")))
                if dd is None or v is None:
                    continue
                try:
                    rows.append((dd, float(v)))
                except (TypeError, ValueError):
                    continue
    return rows


_XVENUE_SCAN_LINE_RE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2})\s+n=\s*(\d+)\s+mean\|gap\|=\s*([\-+]?[\d.]+)c\s+"
    r"mean_pnl=\s*([\-+]?[\d.]+)c"
)


def load_xvenue_scan_txt(path: str):
    """Parse the per-day breakdown lines out of xvenue_scan.txt for a descriptive (not a
    forward-track) day-clustered read -- this is HISTORICAL/retrospective, not a live
    forward paper-track, so its verdict is informational only (see XVENUE_FINDINGS.md).
    Uses a regex (not .split()) because the fixed-width `n=%3d` / `mean_pnl=%+6.2f` padding
    in the scan text inserts whitespace INSIDE what looks like one field."""
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for line in f:
            m = _XVENUE_SCAN_LINE_RE.match(line)
            if not m:
                continue
            d = to_date(m.group(1))
            try:
                v = float(m.group(4))
            except ValueError:
                continue
            if d is not None:
                rows.append((d, v))
    return rows


def load_generic(path: str, date_col: str | None, value_col: str | None):
    rows = []
    if path.endswith(".jsonl") or path.endswith(".json"):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                dc = date_col or next((c for c in ("date", "day", "settle_ts", "snap_ts", "ts", "t")
                                        if c in d), None)
                vc = value_col or next((c for c in ("pnl", "pnl_per_contract", "pnl_gross_c", "value")
                                         if c in d), None)
                if dc is None or vc is None:
                    continue
                dd = to_date(d.get(dc))
                try:
                    v = float(d.get(vc))
                except (TypeError, ValueError):
                    continue
                if dd is not None:
                    rows.append((dd, v))
    else:
        with open(path, newline="") as f:
            rdr = csv.DictReader(f)
            fns = rdr.fieldnames or []
            dc = date_col or next((c for c in ("date", "day", "settle_ts", "snap_ts", "ts") if c in fns), None)
            vc = value_col or next((c for c in ("pnl", "pnl_per_contract", "pnl_gross_c", "value") if c in fns), None)
            for r in rdr:
                if dc is None or vc is None:
                    continue
                dd = to_date(r.get(dc))
                try:
                    v = float(r.get(vc))
                except (TypeError, ValueError):
                    continue
                if dd is not None:
                    rows.append((dd, v))
    return rows


# --------------------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------------------
def day_cluster(rows):
    by_day = defaultdict(list)
    for d, v in rows:
        by_day[d].append(v)
    return {d: statistics.mean(vs) for d, vs in by_day.items()}


def verdict(rows, null: float = 0.0, min_days: int = 14, t_bar: float = 3.0, pos_bar: float = 0.80):
    means = day_cluster(rows)
    n_days = len(means)
    xs = list(means.values())
    out = dict(n_rows=len(rows), n_days=n_days, null=null)
    if n_days == 0:
        out.update(verdict="WAIT", reason="no scoreable rows")
        return out
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if n_days > 1 else 0.0
    se = sd / math.sqrt(n_days) if n_days > 1 else float("nan")
    t = (m - null) / se if se and se > 0 else float("nan")
    pct_pos = sum(1 for x in xs if x > null) / n_days
    out.update(mean_day=m, stdev_day=sd, t=t, pct_positive=pct_pos)
    if n_days < min_days:
        out.update(verdict="WAIT", reason=f"only {n_days} forward days (<{min_days} required)")
    elif not math.isnan(t) and t >= t_bar and pct_pos >= pos_bar:
        out.update(verdict="PASS", reason=f"t={t:.2f}>={t_bar}, %pos={pct_pos:.0%}>={pos_bar:.0%}")
    else:
        tt = f"{t:.2f}" if not math.isnan(t) else "n/a"
        out.update(verdict="FAIL", reason=f"t={tt} (need >={t_bar}), %pos={pct_pos:.0%} (need >={pos_bar:.0%})")
    return out


def print_verdict(name, v):
    print(f"\n=== {name} ===")
    print(f"  n_rows={v['n_rows']}  n_forward_days={v['n_days']}  null={v['null']}")
    if v["n_days"] > 0:
        t = v.get("t")
        tt = f"{t:.2f}" if isinstance(t, float) and not math.isnan(t) else "n/a"
        print(f"  mean/day={v['mean_day']:+.3f}  stdev/day={v['stdev_day']:.3f}  "
              f"day-clustered t={tt}  %days positive={v['pct_positive']:.1%}")
    print(f"  VERDICT: {v['verdict']}  ({v['reason']})")


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def cmd_score(args):
    kind = args.kind
    if kind == "auto":
        base = os.path.basename(args.path).lower()
        if "longshot" in base:
            kind = "longshot"
        elif "weather" in base or "clv" in base:
            kind = "weather"
        elif "xvenue" in base and base.endswith(".txt"):
            kind = "xvenue-scan"
        elif "xvenue" in base:
            kind = "xvenue"
        else:
            kind = "generic"

    if kind == "longshot":
        rows = load_longshot(args.path)
    elif kind == "weather":
        rows, n_total = load_weather_clv(args.path)
        eprint(f"[edge_verdicts] weather CLV log: {n_total} total snapshot rows, "
              f"{len(rows)} settlement-joined+signal rows scoreable")
    elif kind == "xvenue":
        rows = load_xvenue_jsonl([args.path])
    elif kind == "xvenue-scan":
        rows = load_xvenue_scan_txt(args.path)
    else:
        rows = load_generic(args.path, args.date_col, args.value_col)

    v = verdict(rows, null=args.null)
    print_verdict(f"{kind}: {args.path}", v)
    return v


def cmd_auto(args):
    data_dir = args.data_dir
    results = {}

    ls_path = os.path.join(data_dir, "longshot", "longshot_settled.csv")
    rows = load_longshot(ls_path)
    v = verdict(rows, null=0.0)
    v["path"] = ls_path
    v["exists"] = os.path.exists(ls_path)
    results["kalshi-longshot"] = v
    print_verdict(f"kalshi-longshot ({ls_path}, exists={v['exists']})", v)
    if not v["exists"]:
        print("  -> longshot_settled.csv not present yet: collector is active (see "
              "longshot_pending.json) but nothing has SETTLED yet (see script docstring).")

    wx_path = os.path.join(data_dir, "weather", "weather_clv_log.csv")
    rows, n_total = load_weather_clv(wx_path)
    v = verdict(rows, null=0.0)
    v["path"] = wx_path
    v["exists"] = os.path.exists(wx_path)
    v["n_snapshot_rows"] = n_total
    results["kalshi-weather"] = v
    print_verdict(f"kalshi-weather CLV ({wx_path}, {n_total} snapshot rows)", v)
    if v["n_days"] == 0 and n_total > 0:
        print("  -> collector logs snapshots but never fills actual_high/settled -- "
              "see edge_verdicts.py module docstring for the exact gap.")

    xv_paths = sorted(glob.glob(os.path.join(data_dir, "xvenue_*.jsonl")))
    rows = load_xvenue_jsonl(xv_paths)
    v = verdict(rows, null=0.0)
    v["paths"] = xv_paths
    results["xvenue"] = v
    print_verdict(f"xvenue incremental ({len(xv_paths)} files under {data_dir}/xvenue_*.jsonl)", v)
    if not xv_paths:
        print("  -> incremental mode is intentionally disabled by cross_venue_gap.py "
              "(different-tenor venues, not same-event -- see XVENUE_FINDINGS.md).")
        scan_path = os.path.join(data_dir, "xvenue_scan.txt")
        if os.path.exists(scan_path):
            hrows = load_xvenue_scan_txt(scan_path)
            hv = verdict(hrows, null=0.0)
            hv["path"] = scan_path
            results["xvenue-historical-scan (informational only, not a forward track)"] = hv
            print_verdict(f"xvenue HISTORICAL scan, informational only, NOT a forward "
                          f"paper-track ({scan_path})", hv)

    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("score", help="score a single dated P&L file against the forward bar")
    sp.add_argument("path")
    sp.add_argument("--kind", default="auto",
                    choices=["auto", "longshot", "weather", "xvenue", "xvenue-scan", "generic"])
    sp.add_argument("--date-col", default=None)
    sp.add_argument("--value-col", default=None)
    sp.add_argument("--null", type=float, default=0.0)

    ap_auto = sub.add_parser("auto", help="discover + score all known dormant streams under gha_data/")
    ap_auto.add_argument("--data-dir", default="gha_data")

    args = ap.parse_args()
    if args.cmd == "score":
        cmd_score(args)
    elif args.cmd == "auto":
        cmd_auto(args)


if __name__ == "__main__":
    main()
