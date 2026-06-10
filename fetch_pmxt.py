"""Discover Polymarket 15-minute BTC "Up" tokens and pull their top-of-book.

    python fetch_pmxt.py --start 2026-04-14T00 --end 2026-04-16T00

Steps:
  1. discover_btc_15m_up_tokens(): for every 900-s UTC window in [start, end) ask
     Gamma for the event slug  btc-updown-15m-<unix_window_start>  and take
     market.clobTokenIds[0] as the UP token. (VERIFIED against live Gamma:
     outcomes == ["Up","Down"], so index 0 is Up/Yes, and the slug timestamp is
     the UTC window start with endDate == start + 900. Re-confirm against
     https://docs.polymarket.com if the schema changes.)
  2. Pull top-of-book for those asset_ids from the pmxt v2 archive (DuckDB/httpfs).
  3. Write up_book.parquet (timestamp, best_bid, best_ask, asset_id, fee_rate_bps)
     and up_windows.parquet (window_start, window_end, asset_id, condition_id,
     resolved_up) for boundary + label cross-checks in run_real.py.
  4. Print columns, dtypes, timestamp unit, and the fee_rate_bps it found.

READ-ONLY: only public Gamma + the free archive are touched; no auth, no orders.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import pandas as pd
import requests

import pmxt_archive as arch

GAMMA = "https://gamma-api.polymarket.com"
WINDOW_S = 900
EXPECTED_FEE_BPS = 700                  # spec expectation; we VERIFY and report actual


def _parse(h):
    return datetime.strptime(h, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


def _jl(x):
    return json.loads(x) if isinstance(x, str) else x


def discover_btc_15m_up_tokens(start_dt, end_dt, session):
    """Return DataFrame[window_start, window_end, asset_id, condition_id, resolved_up]."""
    t0 = int(start_dt.timestamp()); t1 = int(end_dt.timestamp())
    starts = range(t0 - (t0 % WINDOW_S), t1, WINDOW_S)
    rows, missing, checked = [], 0, 0
    for ts in starts:
        slug = f"btc-updown-15m-{ts}"
        try:
            r = session.get(GAMMA + "/events", params={"slug": slug}, timeout=30)
            ev = r.json()
        except Exception:                          # noqa: BLE001
            ev = None
        if not ev:
            missing += 1
            continue
        m = ev[0]["markets"][0]
        outs = _jl(m.get("outcomes"))
        toks = _jl(m.get("clobTokenIds"))
        if not outs or not toks:
            missing += 1
            continue
        # VERIFY ordering: outcome 0 must be "Up" (else we'd mislabel the token).
        if str(outs[0]).lower() not in ("up", "yes"):
            raise SystemExit(f"STOP: unexpected outcome ordering for {slug}: {outs}")
        checked += 1
        prices = _jl(m.get("outcomePrices")) or []
        resolved_up = None
        if m.get("closed") and prices:
            resolved_up = 1 if float(prices[0]) > 0.5 else 0
        rows.append({
            "window_start": ts, "window_end": ts + WINDOW_S,
            "asset_id": str(toks[0]), "condition_id": m.get("conditionId"),
            "resolved_up": resolved_up,
        })
    df = pd.DataFrame(rows)
    print(f"  discovered {len(df)} windows  (missing {missing}, outcome-order verified on {checked})")
    if df.empty:
        raise SystemExit("STOP: no btc-updown-15m markets found in range -- "
                         "coverage gap or slug pattern changed.")
    # Boundary sanity (step 6a): slug ts is 900-aligned UTC by construction.
    bad = df[df["window_start"] % WINDOW_S != 0]
    if len(bad):
        raise SystemExit("STOP: non-900-aligned window starts found.")
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", required=True, help="UTC hour, YYYY-MM-DDTHH (inclusive)")
    ap.add_argument("--end", required=True, help="UTC hour, YYYY-MM-DDTHH (exclusive)")
    ap.add_argument("--book_out", default="up_book.parquet")
    ap.add_argument("--windows_out", default="up_windows.parquet")
    args = ap.parse_args()

    start_dt, end_dt = _parse(args.start), _parse(args.end)
    print(f"=== fetch_pmxt.py  [{start_dt} .. {end_dt})  UTC ===")

    # Reuse a previous discovery if present (the Gamma step is deterministic).
    import os
    if os.path.exists(args.windows_out):
        win = pd.read_parquet(args.windows_out)
        print(f"  reusing {args.windows_out}: {len(win)} discovered windows")
    else:
        sess = requests.Session()
        win = discover_btc_15m_up_tokens(start_dt, end_dt, sess)
        win.to_parquet(args.windows_out, index=False)

    # Show a few slug-derived boundaries (UTC) for the manual cross-check.
    print("  sample windows (UTC start -> end):")
    for _, r in win.head(3).iterrows():
        print(f"    {datetime.fromtimestamp(r.window_start,timezone.utc)} -> "
              f"{datetime.fromtimestamp(r.window_end,timezone.utc)}  "
              f"resolved_up={r.resolved_up}")

    asset_ids = win["asset_id"].astype(str).tolist()
    con = arch.connect()
    keys = arch.hour_keys(start_dt, _parse(args.end))
    part_dir = "data_book"
    os.makedirs(part_dir, exist_ok=True)
    print(f"  pulling top-of-book from {len(keys)} hourly archive files "
          f"(streaming to disk via DuckDB COPY)...")
    total = 0
    for k in keys:
        out = os.path.join(part_dir, f"{k}.parquet")
        n = arch.fetch_hour_to_parquet(con, k, asset_ids, out)
        total += max(n, 0)
        print(f"    {k}: {n} rows", flush=True)
    if total == 0:
        raise SystemExit("STOP: archive returned no top-of-book rows for these tokens.")

    n_book = arch.merge_parquets(con, os.path.join(part_dir, "*.parquet"), args.book_out)
    print(f"\n  wrote {args.book_out}: {n_book} rows (merged {len(keys)} hours)")

    # Schema from parquet metadata (no full load).
    import pyarrow.parquet as pq
    sc = pq.ParquetFile(args.book_out).schema_arrow
    print("  columns / dtypes:")
    for f in sc:
        print(f"    {f.name}: {f.type}")
    tmin, tmax = con.execute(
        f"SELECT epoch_ms(min(timestamp)), epoch_ms(max(timestamp)) "
        f"FROM read_parquet('{args.book_out}')").fetchone()
    print(f"  timestamp unit: ms (UTC)   range "
          f"{datetime.fromtimestamp(tmin/1000, timezone.utc)} .. "
          f"{datetime.fromtimestamp(tmax/1000, timezone.utc)}")

    # Fee lives on trade prints, not top-of-book rows: probe and VERIFY vs spec.
    fee = arch.trade_print_fee(con, keys[len(keys) // 2], asset_ids)
    if fee is not None:
        print(f"  fee_rate_bps (trade prints): median={fee:.0f}  ({fee/1e4:.2f})")
        if abs(fee - EXPECTED_FEE_BPS) > 100:
            print(f"  *** WARNING: fee_rate_bps {fee:.0f} != spec-expected ~{EXPECTED_FEE_BPS}. "
                  f"Market identity was verified independently (slug->conditionId->asset_id), "
                  f"so this is the REAL fee; run_real.py uses {fee:.0f}. ***")
    else:
        print("  fee_rate_bps: could not probe trade prints; run_real default applies.")


if __name__ == "__main__":
    main()
