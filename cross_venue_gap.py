#!/usr/bin/env python3
"""cross_venue_gap.py -- Kalshi 15m BTC vs Polymarket 5m BTC-updown: cross-venue quote gap.

WHY: gha-data collects two dormant crypto streams that were never actually compared against
each other on their REAL formats: Kalshi's `book_kalshi_btc15m_r*.jsonl.gz` (full order-book
snapshots, one Kalshi market per 15-minute window) and Polymarket's `pmkt_btc_updown_r*.jsonl.gz`
(bid/ask snapshots, one Polymarket market per 5-minute window). This script inspects the ACTUAL
collected formats (see FORMATS below), aligns quotes, and honestly scores whether a tradeable
cross-venue gap exists net of round-trip cost.

FORMATS FOUND (inspected directly from gha-data, 2026-07-10):
  Kalshi book row:
    {"type":"meta","t":..,"ws":<window_open_epoch>,"asset":"btc","tenor_min":15,
     "meta":{"ticker":"KXBTC15M-...","floor_strike":63193.52,"strike_type":"greater_or_equal",
             "yes_bid_dollars":"0.54","yes_ask_dollars":"0.55", ...}}
    {"type":"book","t":..,"ws":..,"spot":63195.27,
     "yes":[[price,size],...] (bid-side depth, ascending price -> best yes bid = max price),
     "no": [[price,size],...] (bid-side depth for NO -> yes ask = 1 - max(no price))}
    {"type":"stat","t":..,"ws":..,"last_price":0.55, ...}
    Window = 15 minutes. `ws` values step by exactly 900s. `floor_strike` ~= spot at window
    open (an ATM greater_or_equal strike) -- confirmed floor_strike (63193.52) essentially
    equal to concurrent `spot` (63195.27) 44s into the window.

  Polymarket row (pmkt_btc_updown_r*.jsonl.gz):
    {"t":.., "end":.., "venue":"polymarket", "asset":"btc",
     "slug":"btc-updown-5m-<window_open_epoch>",
     "up_bid":0.58,"up_ask":0.61,"down_bid":0.40,"down_ask":0.41, "up_bsz":..,"up_asz":.., ...}
    Window = 5 minutes. slug epochs step by exactly 300s. This is BTC-only -- no
    pmkt_eth/sol/xrp_updown stream exists in gha-data (checked multiple days).

  KEY FINDING: window tenors differ (15m Kalshi vs 5m Polymarket) and Kalshi has no 5m crypto
  market collected. Only 1-in-3 Polymarket 5m windows shares a wall-clock OPEN time with a
  Kalshi 15m window (`slug_epoch == ws`); when it does, both markets are ATM at that shared t0,
  so a genuine SAME-TIME quote comparison is possible. But the two markets still resolve at
  DIFFERENT times (t0+300 for Polymarket vs t0+900 for Kalshi) -- i.e. they are NOT the same
  event, just two different-horizon bets sharing a reference price. See XVENUE_FINDINGS.md for
  the full argument and why this means (b) (forward paper-tracking as an "edge candidate") is
  skipped even though (a) (the historical scan below) is still produced as honest diagnostic
  evidence.

USAGE:
  python cross_venue_gap.py scan  [--data-dir gha_data] [--days N] [--out gha_data/xvenue_scan.txt]
  python cross_venue_gap.py incremental ...   # see XVENUE_FINDINGS.md: intentionally disabled
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict

ASSET = "btc"
KALSHI_TENOR_S = 900          # 15 min
PMKT_TENOR_S = 300            # 5 min
ENTRY_TOL_S = 90              # max allowed gap between "entry" samples on the two venues
COST_THRESHOLDS_C = (1.0, 2.0, 3.0)   # cent thresholds swept (Kalshi ~1c spread; PM parametrized)

_RE_T = re.compile(r'"t":\s*([\-0-9.eE]+)')
_RE_WS = re.compile(r'"ws":\s*([\-0-9]+)')
_RE_SPOT = re.compile(r'"spot":\s*([\-0-9.eE]+)')
_RE_TYPE = re.compile(r'"type":\s*"(\w+)"')


def eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)
    sys.stderr.flush()


# --------------------------------------------------------------------------------------
# Data acquisition: shallow-fetch gha-data if not already checked out locally.
# --------------------------------------------------------------------------------------
def ensure_data_dir(data_dir: str) -> str:
    """Return a path to a gha_data/ tree with day-dirs. If `data_dir` already has day-dirs,
    use it as-is (fast path: caller already checked out gha-data). Otherwise shallow-fetch
    origin/gha-data into a temp worktree-free checkout and return that path."""
    if os.path.isdir(data_dir) and any(re.match(r"^\d{4}-\d{2}-\d{2}$", n) for n in os.listdir(data_dir)):
        return data_dir
    eprint(f"[cross_venue_gap] {data_dir!r} has no day-dirs yet -- shallow-fetching origin/gha-data ...")
    tmp = tempfile.mkdtemp(prefix="gha_data_")
    subprocess.run(["git", "fetch", "--depth=1", "origin", "gha-data"], check=True)
    subprocess.run(["git", "--work-tree=" + tmp, "checkout", "FETCH_HEAD", "--", "gha_data"], check=True)
    out = os.path.join(tmp, "gha_data")
    eprint(f"[cross_venue_gap] fetched into {out}")
    return out


def day_dirs(data_dir: str, limit: int | None = None) -> list[str]:
    days = sorted(n for n in os.listdir(data_dir) if re.match(r"^\d{4}-\d{2}-\d{2}$", n))
    if limit:
        days = days[-limit:]
    return days


# --------------------------------------------------------------------------------------
# Per-day parsing
# --------------------------------------------------------------------------------------
def best_from_levels(levels):
    """levels: list of [price, size] resting-order depth, ascending price. Best = max price
    with size > 0 (mirrors kalshi_weather_snapshot.parse_book's `best()` convention)."""
    best_p = None
    for p, s in levels:
        if s and s > 0 and (best_p is None or p > best_p):
            best_p = p
    return best_p


def parse_kalshi_day(day_dir: str):
    """Returns (windows, spot_series) for one day, btc-15m only.
    windows: {ws: {"floor_strike": float|None, "entry_t": float, "yes_bid": float, "yes_ask": float}}
    spot_series: sorted list of (t, spot) -- deduped, used for settlement lookups.
    """
    windows: dict[int, dict] = {}
    spot_pairs: list[tuple[float, float]] = []
    files = sorted(f for f in os.listdir(day_dir) if re.match(rf"^book_kalshi_{ASSET}15m_r\d+\.jsonl\.gz$", f))
    for fn in files:
        path = os.path.join(day_dir, fn)
        try:
            with gzip.open(path, "rt") as fh:
                for line in fh:
                    m = _RE_TYPE.search(line)
                    if not m:
                        continue
                    typ = m.group(1)
                    if typ == "meta":
                        try:
                            d = json.loads(line)
                        except Exception:
                            continue
                        ws = d.get("ws")
                        fs = (d.get("meta") or {}).get("floor_strike")
                        if ws is not None:
                            w = windows.setdefault(int(ws), {})
                            if fs is not None and "floor_strike" not in w:
                                w["floor_strike"] = float(fs)
                    elif typ == "book":
                        mt = _RE_T.search(line)
                        mws = _RE_WS.search(line)
                        msp = _RE_SPOT.search(line)
                        if not (mt and mws):
                            continue
                        t = float(mt.group(1))
                        ws = int(mws.group(1))
                        if msp:
                            spot_pairs.append((t, float(msp.group(1))))
                        w = windows.setdefault(ws, {})
                        if "entry_t" not in w:
                            # first book row seen for this window -> full-parse for top-of-book
                            try:
                                d = json.loads(line)
                            except Exception:
                                continue
                            yb = best_from_levels(d.get("yes") or [])
                            no_b = best_from_levels(d.get("no") or [])
                            if yb is None or no_b is None:
                                continue
                            w["entry_t"] = t
                            w["yes_bid"] = yb
                            w["yes_ask"] = round(1.0 - no_b, 6)
        except (OSError, EOFError, gzip.BadGzipFile) as e:
            eprint(f"  [warn] skip {path}: {e}")
    spot_pairs.sort()
    # dedupe consecutive identical timestamps (keep last)
    spot_series = []
    for t, s in spot_pairs:
        if spot_series and spot_series[-1][0] == t:
            spot_series[-1] = (t, s)
        else:
            spot_series.append((t, s))
    return windows, spot_series


def parse_pmkt_day(day_dir: str):
    """Returns {slug_epoch: {"entry_t":.., "up_bid":.., "up_ask":.., "down_bid":.., "down_ask":..}}"""
    windows: dict[int, dict] = {}
    files = sorted(f for f in os.listdir(day_dir) if re.match(rf"^pmkt_{ASSET}_updown_r\d+\.jsonl\.gz$", f))
    for fn in files:
        path = os.path.join(day_dir, fn)
        try:
            with gzip.open(path, "rt") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    slug = d.get("slug") or ""
                    m = re.search(r"(\d+)$", slug)
                    if not m:
                        continue
                    epoch = int(m.group(1))
                    w = windows.setdefault(epoch, {})
                    if "entry_t" not in w:
                        try:
                            w["entry_t"] = float(d["t"])
                            w["up_bid"] = float(d["up_bid"])
                            w["up_ask"] = float(d["up_ask"])
                            w["down_bid"] = float(d["down_bid"])
                            w["down_ask"] = float(d["down_ask"])
                        except (KeyError, TypeError, ValueError):
                            w.pop("entry_t", None)
        except (OSError, EOFError, gzip.BadGzipFile) as e:
            eprint(f"  [warn] skip {path}: {e}")
    return windows


def spot_at(spot_series, t):
    """Nearest spot sample to time t (spot_series sorted list of (t,spot)); None if empty
    or nearest sample is >5min away (stale)."""
    if not spot_series:
        return None
    ts = [x[0] for x in spot_series]
    i = bisect.bisect_left(ts, t)
    cands = []
    if i < len(ts):
        cands.append(spot_series[i])
    if i > 0:
        cands.append(spot_series[i - 1])
    if not cands:
        return None
    best = min(cands, key=lambda x: abs(x[0] - t))
    if abs(best[0] - t) > 300:
        return None
    return best[1]


# --------------------------------------------------------------------------------------
# Per-day alignment + scoring
# --------------------------------------------------------------------------------------
def score_day(day: str, day_dir: str):
    kw, spot_series = parse_kalshi_day(day_dir)
    pw = parse_pmkt_day(day_dir)
    rows = []
    shared = sorted(set(kw) & set(pw))
    for ws in shared:
        k = kw[ws]
        p = pw[ws]
        if "entry_t" not in k or "entry_t" not in p:
            continue
        if abs(k["entry_t"] - p["entry_t"]) > ENTRY_TOL_S:
            continue
        k_mid = (k["yes_bid"] + k["yes_ask"]) / 2.0
        p_mid = (p["up_bid"] + p["up_ask"]) / 2.0
        gap_c = (p_mid - k_mid) * 100.0

        strike = k.get("floor_strike")
        s_open = spot_at(spot_series, ws)
        if strike is None:
            strike = s_open
        s_k_close = spot_at(spot_series, ws + KALSHI_TENOR_S)
        s_p_close = spot_at(spot_series, ws + PMKT_TENOR_S)
        if strike is None or s_k_close is None or s_open is None or s_p_close is None:
            continue
        kalshi_up = 1.0 if s_k_close >= strike else 0.0
        pmkt_up = 1.0 if s_p_close > s_open else 0.0

        # "take the cheap venue, exit at settle": buy UP wherever the ask is lower; each venue
        # settles against ITS OWN outcome (different horizons -- see docstring/findings: this
        # is directional single-leg exposure, NOT a hedged locked box).
        if k["yes_ask"] <= p["up_ask"]:
            venue, entry, outcome = "kalshi", k["yes_ask"], kalshi_up
        else:
            venue, entry, outcome = "pmkt", p["up_ask"], pmkt_up
        pnl_gross_c = (outcome - entry) * 100.0

        rows.append(dict(day=day, ws=ws, gap_c=gap_c, abs_gap_c=abs(gap_c),
                          venue=venue, entry=entry, outcome=outcome, pnl_gross_c=pnl_gross_c,
                          kalshi_up=kalshi_up, pmkt_up=pmkt_up))
    return dict(day=day, n_kalshi_windows=len(kw), n_pmkt_windows=len(pw),
                n_shared_open_t0=len(shared), rows=rows)


def pct(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
    return xs[i]


def run_scan(data_dir: str, out_path: str, days_limit: int | None):
    data_dir = ensure_data_dir(data_dir)
    days = day_dirs(data_dir, days_limit)
    eprint(f"[cross_venue_gap] scanning {len(days)} day-dirs under {data_dir} ...")
    per_day = []
    for i, day in enumerate(days):
        dd = os.path.join(data_dir, day)
        res = score_day(day, dd)
        per_day.append(res)
        eprint(f"  [{i+1}/{len(days)}] {day}: kalshi_windows={res['n_kalshi_windows']} "
              f"pmkt_windows={res['n_pmkt_windows']} shared_open_t0={res['n_shared_open_t0']} "
              f"aligned={len(res['rows'])}")

    all_rows = [r for d in per_day for r in d["rows"]]
    n_kalshi_windows = sum(d["n_kalshi_windows"] for d in per_day)
    n_pmkt_windows = sum(d["n_pmkt_windows"] for d in per_day)
    n_shared_t0 = sum(d["n_shared_open_t0"] for d in per_day)

    lines = []
    lines.append("=" * 88)
    lines.append("cross_venue_gap.py -- Kalshi 15m BTC vs Polymarket 5m BTC-updown historical scan")
    lines.append("=" * 88)
    lines.append(f"days scanned: {len(days)}  ({days[0] if days else '-'} .. {days[-1] if days else '-'})")
    lines.append(f"total Kalshi btc15m windows seen: {n_kalshi_windows}")
    lines.append(f"total Polymarket btc-updown-5m windows seen: {n_pmkt_windows}")
    lines.append(f"windows sharing an OPEN t0 across venues (1-in-3 PM windows, by construction): {n_shared_t0}")
    lines.append(f"windows with a usable ALIGNED same-time quote pair (both venues quoted within "
                 f"{ENTRY_TOL_S}s of shared t0, settlement resolvable): {len(all_rows)}")
    lines.append("")
    lines.append("NOTE: 'aligned' here means SAME START TIME, not SAME EVENT -- Kalshi resolves the")
    lines.append("window at t0+900s, Polymarket at t0+300s. See XVENUE_FINDINGS.md for why this blocks")
    lines.append("a genuine cross-venue arbitrage read; the numbers below are still reported honestly")
    lines.append("as a same-time quote-divergence diagnostic.")
    lines.append("")

    if all_rows:
        gaps = [r["abs_gap_c"] for r in all_rows]
        signed = [r["gap_c"] for r in all_rows]
        lines.append("-- gap distribution |P(up)_pmkt - P(up)_kalshi| at shared t0, cents --")
        lines.append(f"  n={len(gaps)}  mean={statistics.mean(gaps):.2f}c  median={statistics.median(gaps):.2f}c "
                     f"stdev={statistics.pstdev(gaps):.2f}c")
        lines.append(f"  p10={pct(gaps,.10):.2f}c  p90={pct(gaps,.90):.2f}c  p99={pct(gaps,.99):.2f}c  "
                     f"max={max(gaps):.2f}c")
        lines.append(f"  signed mean (pmkt - kalshi): {statistics.mean(signed):+.2f}c "
                     f"(sign consistency: {sum(1 for x in signed if x>0)}/{len(signed)} pmkt-rich)")
        lines.append("")
        lines.append("-- n windows with |gap| exceeding an assumed round-trip-cost threshold --")
        lines.append("   (Kalshi ~1c spread is the stated baseline; Polymarket taker fee ~0.07*p*(1-p) is")
        lines.append("    parametrized separately -- see fees.py -- these thresholds are the TOTAL")
        lines.append("    assumed round-trip cost in cents, swept at 1c/2c/3c)")
        for c in COST_THRESHOLDS_C:
            n = sum(1 for g in gaps if g > c)
            lines.append(f"    > {c:.0f}c: {n}/{len(gaps)} ({100.0*n/len(gaps):.1f}%)")
        lines.append("")
        pnl = [r["pnl_gross_c"] for r in all_rows]
        n_pos = sum(1 for x in pnl if x > 0)
        lines.append("-- would-be paper P&L: 'take the cheap venue (lower UP ask), exit at that venue's")
        lines.append("   own settlement' -- SINGLE-LEG DIRECTIONAL exposure, NOT a hedged locked box")
        lines.append("   (see caveat above: the two venues do not share a resolution time) --")
        lines.append(f"  n={len(pnl)}  mean={statistics.mean(pnl):+.2f}c/contract  "
                     f"total={sum(pnl):+.1f}c  %days positive-mean not applicable per-row; "
                     f"%rows positive={100.0*n_pos/len(pnl):.1f}%")
        by_venue = defaultdict(list)
        for r in all_rows:
            by_venue[r["venue"]].append(r["pnl_gross_c"])
        for v, xs in sorted(by_venue.items()):
            lines.append(f"    chose {v}: n={len(xs)}  mean={statistics.mean(xs):+.2f}c  "
                         f"%pos={100.0*sum(1 for x in xs if x>0)/len(xs):.1f}%")
        lines.append("")
        lines.append("-- per-day breakdown (day, n_aligned, mean_abs_gap_c, mean_pnl_c) --")
        for d in per_day:
            if not d["rows"]:
                continue
            g = [r["abs_gap_c"] for r in d["rows"]]
            p = [r["pnl_gross_c"] for r in d["rows"]]
            lines.append(f"  {d['day']}  n={len(d['rows']):3d}  mean|gap|={statistics.mean(g):5.2f}c  "
                         f"mean_pnl={statistics.mean(p):+6.2f}c")
    else:
        lines.append("NO aligned same-time windows found across the scanned days.")

    lines.append("")
    lines.append("Verdict: see XVENUE_FINDINGS.md for the full same-event-vs-same-time argument and")
    lines.append("why incremental forward paper-tracking (b) is intentionally NOT wired up.")
    text = "\n".join(lines) + "\n"

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write(text)
    print(text)
    print(f"[cross_venue_gap] wrote {out_path}")
    return per_day


def run_incremental(*_a, **_kw):
    msg = (
        "[cross_venue_gap] incremental mode (b) is intentionally DISABLED.\n"
        "Kalshi btc15m and Polymarket btc-updown-5m are different-tenor, different-resolution-time\n"
        "markets (see docstring + XVENUE_FINDINGS.md): a 'gap' between them is a term-structure /\n"
        "implied-vol difference, not a same-event mispricing, so it cannot be forward-tracked as an\n"
        "'edge candidate' under the pre-registered same-event bar without misrepresenting directional\n"
        "exposure as arbitrage. Run `python cross_venue_gap.py scan` for the historical diagnostic.\n"
    )
    eprint(msg)
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    sp = sub.add_parser("scan", help="historical scan over all available days -> xvenue_scan.txt")
    sp.add_argument("--data-dir", default="gha_data")
    sp.add_argument("--out", default="gha_data/xvenue_scan.txt")
    sp.add_argument("--days", type=int, default=None, help="limit to the most recent N days (default: all)")

    ip = sub.add_parser("incremental", help="(disabled -- see XVENUE_FINDINGS.md)")
    ip.add_argument("--data-dir", default="gha_data")
    ip.add_argument("--date", default=None)

    args = ap.parse_args()
    if args.mode == "scan":
        run_scan(args.data_dir, args.out, args.days)
    elif args.mode == "incremental":
        sys.exit(run_incremental())


if __name__ == "__main__":
    main()
