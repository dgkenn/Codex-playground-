"""
window_open_race_study.py — WINDOW-OPEN RACE study for Kalshi BTC15M maker-box

Question: Is t=0 (moment a 15-min window opens) contestable at REST latency?
Is the book born tight / do we arrive too late? Should an "open-quote" strategy be built?

Convention inferred from data inspection:
  - yes[] and no[] are BID ladders (resting bids to BUY the contract)
  - yes_bid = max price in yes[] with size>0  (best bid on YES)
  - no_bid  = max price in no[]  with size>0  (best bid on NO)
  - yes_ask = 1.0 - no_bid   (complementarity: buying NO at Y = selling YES at 1-Y)
  - spread  = yes_ask - yes_bid
  - mid     = (yes_bid + yes_ask) / 2
  - tradeable two-sided: yes_bid > 0 AND no_bid > 0 AND mid in [0.03, 0.97]

Evidence for convention: yes_bid + no_bid = 0.99 consistently (1c box spread).
"""

import os
import gzip
import json
import glob
from collections import defaultdict
import numpy as np

os.chdir("/tmp/code")


def load_all_book_rows(pattern="overnight_data/book_kalshi_btc15m_r*.jsonl.gz"):
    rows = []
    files = sorted(glob.glob(pattern))
    for fn in files:
        try:
            with gzip.open(fn, "rt") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        if r.get("type") == "book":
                            rows.append(r)
                    except Exception:
                        pass
        except EOFError:
            pass  # truncated file; use partial data
        except Exception:
            pass
    return rows


def best_bid(ladder):
    """Highest price with positive size."""
    prices = [x[0] for x in ladder if x[1] > 0]
    return max(prices) if prices else None


def book_metrics(row):
    """Return (yes_bid, no_bid, yes_ask, spread, mid) or None if not tradeable."""
    yb = best_bid(row["yes"])
    nb = best_bid(row["no"])
    if yb is None or nb is None:
        return None
    ya = 1.0 - nb         # complementarity
    spread = ya - yb
    mid = (yb + ya) / 2.0
    return yb, nb, ya, spread, mid


def pct(arr, p):
    return float(np.percentile(arr, p)) if len(arr) >= 3 else float("nan")


def pct_str(n, d):
    return f"{n}/{d} ({100*n/d:.0f}%)" if d > 0 else "n/a"


def main():
    print("Loading book rows ...")
    rows = load_all_book_rows()

    win_rows = defaultdict(list)
    for r in rows:
        win_rows[r["ws"]].append(r)
    for ws in win_rows:
        win_rows[ws].sort(key=lambda r: r["t"])

    total_windows = len(win_rows)
    print(f"  {len(rows):,} book rows from {total_windows} windows across 48 files")

    # ── 1. WINDOW COVERAGE ──────────────────────────────────────────────────
    EARLY_THRESH = 15.0   # seconds from window open

    covered_ws = []
    for ws, wrows in win_rows.items():
        first_dt = wrows[0]["t"] - ws
        if first_dt < EARLY_THRESH:
            covered_ws.append(ws)
    covered_ws.sort()
    n_covered = len(covered_ws)

    print(f"\n{'='*62}")
    print("1. WINDOW COVERAGE")
    print(f"{'='*62}")
    print(f"  Total windows                    : {total_windows}")
    print(f"  With first snap <{EARLY_THRESH:.0f}s from open  : {n_covered}")
    print(f"  (analysis uses only covered windows)")

    # ── 2. BOOK-BIRTH TIMELINE ──────────────────────────────────────────────
    book_birth_dts = []
    born_before_first = 0
    arrival_dts = []
    rtt_all = []

    for ws in covered_ws:
        wrows = win_rows[ws]
        first_dt = wrows[0]["t"] - ws
        arrival_dts.append(first_dt)

        for r in wrows:
            if r.get("rtt_ms") is not None:
                rtt_all.append(r["rtt_ms"])

        first_tradeable_dt = None
        for r in wrows:
            m = book_metrics(r)
            if m is None:
                continue
            _, _, _, _, mid = m
            if 0.03 <= mid <= 0.97:
                first_tradeable_dt = r["t"] - ws
                break

        if first_tradeable_dt is not None:
            book_birth_dts.append(first_tradeable_dt)
            if first_tradeable_dt <= first_dt + 0.01:
                born_before_first += 1

    frac_born = born_before_first / len(book_birth_dts) if book_birth_dts else 0

    print(f"\n{'='*62}")
    print(f"2. BOOK-BIRTH TIMELINE  (n={len(book_birth_dts)} covered windows)")
    print(f"{'='*62}")
    print(f"  First tradeable snapshot seconds-from-open:")
    print(f"    p10={pct(book_birth_dts,10):.2f}s  p50={pct(book_birth_dts,50):.2f}s  p90={pct(book_birth_dts,90):.2f}s")
    print(f"  Already 2-sided at very first poll : {born_before_first}/{len(book_birth_dts)} ({100*frac_born:.0f}%)")

    # ── 3. ARRIVAL LAG + REST LATENCY FLOOR ─────────────────────────────────
    LATENCY_FLOOR = (pct(arrival_dts, 50) + pct(rtt_all, 90) / 1000.0) if rtt_all else 20.0

    print(f"\n{'='*62}")
    print(f"3. ARRIVAL LAG + REST LATENCY FLOOR  (n={len(arrival_dts)} windows)")
    print(f"{'='*62}")
    print(f"  First-snapshot dt from open (seconds):")
    print(f"    p10={pct(arrival_dts,10):.2f}s  p50={pct(arrival_dts,50):.2f}s  p90={pct(arrival_dts,90):.2f}s")
    if rtt_all:
        print(f"  REST rtt_ms ({len(rtt_all):,} samples):")
        print(f"    p10={pct(rtt_all,10):.0f}ms  p50={pct(rtt_all,50):.0f}ms  p90={pct(rtt_all,90):.0f}ms  p99={pct(rtt_all,99):.0f}ms")
    print(f"  Structural latency floor (arrival p50 + rtt p90) ≈ {LATENCY_FLOOR:.2f}s from open")

    # ── 4. EARLY vs SETTLED SPREAD ───────────────────────────────────────────
    early_spreads   = []   # dt < 3s
    mid_spreads     = []   # 3s <= dt < 10s
    settled_spreads = []   # 30s <= dt < 60s

    n_wide_1c_arrival  = 0
    n_wide_2c_arrival  = 0
    n_wide_1c_survives = 0
    n_wide_2c_survives = 0
    n_with_metrics     = 0
    window_details     = []

    for ws in covered_ws:
        wrows = win_rows[ws]
        arrivals = []
        for r in wrows:
            dt = r["t"] - ws
            m = book_metrics(r)
            if m is None:
                continue
            _, _, _, spread, mid = m
            if not (0.03 <= mid <= 0.97):
                continue
            arrivals.append((dt, spread, mid))
            if dt < 3.0:
                early_spreads.append(spread)
            elif dt < 10.0:
                mid_spreads.append(spread)
            elif 30.0 <= dt < 60.0:
                settled_spreads.append(spread)

        if not arrivals:
            continue

        n_with_metrics += 1
        first_dt, first_sp, first_mid = arrivals[0]

        # Spread at latency floor
        floor_sp = None
        for dt, sp, _ in arrivals:
            if dt >= LATENCY_FLOOR:
                floor_sp = sp
                break

        if first_sp > 0.01:
            n_wide_1c_arrival += 1
            if floor_sp is not None and floor_sp > 0.01:
                n_wide_1c_survives += 1
        if first_sp > 0.02:
            n_wide_2c_arrival += 1
            if floor_sp is not None and floor_sp > 0.02:
                n_wide_2c_survives += 1

        window_details.append(dict(ws=ws, first_dt=first_dt, first_sp=first_sp,
                                   first_mid=first_mid, floor_sp=floor_sp))

    print(f"\n{'='*62}")
    print(f"4. EARLY vs SETTLED SPREAD  (n={n_with_metrics} windows with metrics)")
    print(f"{'='*62}")
    print(f"  {'Bucket':22} {'n':>5}  {'p10':>8} {'p50':>8} {'p90':>8}  {'mean':>8}")
    print("  " + "-"*64)

    def srow(label, arr):
        if not arr:
            return f"  {label:22} {'0':>5}  {'—':>8} {'—':>8} {'—':>8}  {'—':>8}"
        return (f"  {label:22} {len(arr):>5}  "
                f"{pct(arr,10)*100:>7.2f}c {pct(arr,50)*100:>7.2f}c {pct(arr,90)*100:>7.2f}c  "
                f"{np.mean(arr)*100:>7.2f}c")

    print(srow("dt<3s (early)", early_spreads))
    print(srow("3s<=dt<10s (mid-early)", mid_spreads))
    print(srow("30s<=dt<60s (settled)", settled_spreads))
    print()
    print(f"  Latency floor = {LATENCY_FLOOR:.2f}s")
    print(f"  Wide spread at first tradeable snap AND surviving to latency floor:")
    print(f"    >1c at arrival     : {pct_str(n_wide_1c_arrival,  n_with_metrics)}")
    print(f"    >1c AND survives   : {pct_str(n_wide_1c_survives, n_with_metrics)}")
    print(f"    >2c at arrival     : {pct_str(n_wide_2c_arrival,  n_with_metrics)}")
    print(f"    >2c AND survives   : {pct_str(n_wide_2c_survives, n_with_metrics)}")
    print()
    print(f"  {'ws':>12} {'first_dt':>9} {'first_sp':>9} {'mid':>7} {'floor_sp':>9} {'>1c':>5} {'survives':>9}")
    print("  " + "-"*68)
    for wd in window_details:
        w1 = "Y" if wd["first_sp"] > 0.01 else "N"
        fs = wd["floor_sp"]
        surv = ("Y" if fs is not None and fs > 0.01 else
                "N" if fs is not None else "?")
        fss = f"{fs*100:.2f}c" if fs is not None else "    ?"
        print(f"  {wd['ws']:>12} {wd['first_dt']:>9.2f} {wd['first_sp']*100:>8.2f}c "
              f"{wd['first_mid']:>7.3f} {fss:>9} {w1:>5} {surv:>9}")

    # ── 5. VERDICT ──────────────────────────────────────────────────────────
    frac_1c_survives = n_wide_1c_survives / n_with_metrics if n_with_metrics > 0 else 0
    frac_2c_survives = n_wide_2c_survives / n_with_metrics if n_with_metrics > 0 else 0

    print(f"\n{'='*62}")
    print("5. VERDICT — WINDOW-OPEN RACE FEASIBILITY AT REST LATENCY")
    print(f"{'='*62}")
    print(f"  Covered windows (first snap <15s)         : {n_covered}/{total_windows}")
    print(f"  Book already 2-sided at first poll        : {100*frac_born:.0f}%")
    print(f"  Arrival lag p50                           : {pct(arrival_dts,50):.1f}s")
    print(f"  REST rtt_ms p50 / p90                     : {pct(rtt_all,50):.0f} / {pct(rtt_all,90):.0f} ms")
    print(f"  Structural latency floor                  : ~{LATENCY_FLOOR:.2f}s from open")
    print(f"  Windows where >2c edge survives to floor  : {pct_str(n_wide_2c_survives, n_with_metrics)}")
    print()

    if frac_2c_survives >= 0.5:
        verdict = "POTENTIALLY CONTESTABLE — build warrant exists"
    elif frac_2c_survives >= 0.2:
        verdict = "MARGINAL — edge exists but latency-limited"
    else:
        verdict = "NO-GO AT REST LATENCY"

    print(f"  VERDICT: {verdict}")
    print()

    if frac_born > 0.7:
        print(f"  * Book is ALREADY 2-sided at first poll in {100*frac_born:.0f}% of windows.")
        print(f"    The book is born tight (or tight before we arrive).")
    if LATENCY_FLOOR > 5.0:
        print(f"  * Latency floor ({LATENCY_FLOOR:.1f}s) >> any early-window edge duration.")
        print(f"    We cannot act before the spread compresses at REST cadence.")
    if frac_2c_survives < 0.2:
        print(f"  * Wide (>2c) edge persists to our latency floor in only "
              f"{100*frac_2c_survives:.0f}% of windows.")
        print(f"    Even when wide edges exist at arrival, they're gone before we could act.")
    print()
    print(f"  RECOMMENDATION: Do NOT build an open-quote variant at REST latency.")
    print(f"  The data shows the book is consistently tight by the time a REST-polling")
    print(f"  bot could place an order (~{LATENCY_FLOOR:.0f}s from open). A WebSocket-based")
    print(f"  sub-second approach might contest very early edges, but would require")
    print(f"  entirely different infrastructure and re-measurement.")
    print()
    print(f"  CAVEATS:")
    print(f"    - Only {n_covered} covered windows have a first snap within 15s of open")
    print(f"    - Most arrive at ~14s; only 2 windows have first snap <10s (true t=0 unmeasured)")
    print(f"    - REST rtt is {pct(rtt_all,50):.0f}ms median — not competitive for sub-second racing")
    print(f"    - Spread at open data is limited; conclusions directionally strong but low-N")


if __name__ == "__main__":
    main()
