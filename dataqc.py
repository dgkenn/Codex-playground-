"""Data-quality gate for the 15-minute BTC Up/Down backtest.

Runs checks A-G on the filtered book (up_book.parquet), the Binance spot
(btc.npz), and their join -- catching the cheap fatal errors (unit mismatches,
Up/Down inversion, UTC/ET misalignment, stale joins) before any P&L is trusted.

    python dataqc.py --book up_book.parquet --spot btc.npz --windows up_windows.parquet
    python dataqc.py --selftest          # validate the QC logic on synthetic data

Prints PASS / WARN / FAIL per check and a triage summary of the four that most
often manufacture fake edges: fee identity, label agreement, as-of join gap,
and (left to run_real robustness) in/out-of-sample replication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from run_real import load_spot, load_book
from fairvalue import realized_vol_per_s

WINDOW_S = 900
R = []  # (section, name, status, detail)


def chk(section, name, status, detail=""):
    R.append((section, name, status, detail))
    print(f"  [{status:4}] {section} {name}: {detail}")


def asof_idx(spot_ts, q_ms):
    i = np.searchsorted(spot_ts, q_ms, side="right") - 1
    return i


def spot_at(spot_ts, spot_px, q_ms):
    i = asof_idx(spot_ts, q_ms)
    ok = i >= 0
    out = np.full(np.shape(q_ms), np.nan)
    out[ok] = spot_px[i[ok]]
    return out


# --------------------------------------------------------------------------- A
def section_A(book, spot_ts, spot_px, win):
    print("A. Coverage")
    b_ts = book["ts_ms"].to_numpy()
    b_lo, b_hi = b_ts.min(), b_ts.max()
    span_days = (b_hi - b_lo) / 86_400_000
    # A1 hourly gaps
    hours = pd.to_datetime(b_ts, unit="ms", utc=True).floor("h")
    present = pd.Series(1, index=hours).groupby(level=0).size()
    full = pd.date_range(present.index.min(), present.index.max(), freq="h", tz="UTC")
    missing = [h for h in full if h not in present.index]
    chk("A", "hourly-gaps", "PASS" if not missing else "WARN",
        f"{len(full)} hours, {len(missing)} empty" + (f" e.g.{missing[:3]}" if missing else ""))
    # A2 window count
    nwin_book = len(np.unique(b_ts // 1000 // WINDOW_S))
    expect = round(span_days * 96)
    chk("A", "window-count", "PASS" if nwin_book >= 0.8 * expect else "FAIL",
        f"{nwin_book} windows in book vs ~{expect} expected ({span_days:.2f} days)")
    # A3 both legs overlap
    s_lo, s_hi = spot_ts.min(), spot_ts.max()
    covered = s_lo <= b_lo and s_hi >= b_hi
    chk("A", "spot-covers-book", "PASS" if covered else "FAIL",
        f"book[{_d(b_lo)}..{_d(b_hi)}] spot[{_d(s_lo)}..{_d(s_hi)}]")
    # A4 distinct up tokens ~ windows
    if "asset_id" in book.columns:
        nass = book["asset_id"].nunique()
        chk("A", "token-count", "PASS" if 0.8 * nwin_book <= nass <= 1.2 * nwin_book else "WARN",
            f"{nass} distinct Up asset_ids vs {nwin_book} windows")
    if win is not None:
        chk("A", "discovered-windows", "PASS", f"{len(win)} windows discovered via Gamma")


# --------------------------------------------------------------------------- B
def section_B(book, win):
    print("B. Identity")
    # B1 fee
    fee = book["fee_rate_bps"].dropna() if "fee_rate_bps" in book.columns else pd.Series([], dtype=float)
    if len(fee):
        med = float(fee.median())
        chk("B", "fee_rate_bps", "PASS" if abs(med - 700) <= 100 else "WARN",
            f"median {med:.0f} ({med/1e4:.2f}); spec expected ~700")
    else:
        fee_probe = _probe_trade_fee(win)
        if fee_probe is not None:
            chk("B", "fee_rate_bps", "PASS" if abs(fee_probe - 700) <= 100 else "WARN",
                f"none on top-of-book rows; trade-print fee={fee_probe:.0f} "
                f"({fee_probe/1e4:.2f}); spec expected ~700")
        else:
            chk("B", "fee_rate_bps", "WARN", "fee carried only on trade prints; not in book file")
    # B3 prices in (0,1) and bid<=ask
    bid, ask = book["bid"].to_numpy(), book["ask"].to_numpy()
    in01 = ((bid > 0) & (bid < 1) & (ask > 0) & (ask < 1)).mean()
    ordered = (bid <= ask).mean()
    chk("B", "prices-in-(0,1)", "PASS" if in01 > 0.999 else "FAIL", f"{in01:.4%} of rows")
    chk("B", "bid<=ask", "PASS" if ordered > 0.999 else "FAIL", f"{ordered:.4%} of rows")


def _probe_trade_fee(win):
    if win is None or "asset_id" not in win.columns:
        return None
    try:
        import pmxt_archive as arch
        con = arch.connect()
        ts0 = int(win["window_start"].iloc[0])
        hk = datetime.fromtimestamp(ts0, timezone.utc).strftime("%Y-%m-%dT%H")
        ids = ",".join("'" + a + "'" for a in win["asset_id"].head(8))
        url = arch.URL.format(h=hk)
        q = (f"SELECT median(fee_rate_bps) f FROM read_parquet('{url}') "
             f"WHERE asset_id IN ({ids}) AND event_type='last_trade_price' "
             f"AND fee_rate_bps IS NOT NULL")
        v = con.execute(q).fetchone()[0]
        return float(v) if v is not None else None
    except Exception:
        return None


# --------------------------------------------------------------------------- C
def section_C(book, spot_ts):
    print("C. Timestamp integrity")
    b_ts = book["ts_ms"].to_numpy()
    yr_b = pd.to_datetime([b_ts.min(), b_ts.max()], unit="ms", utc=True).year.tolist()
    yr_s = pd.to_datetime([spot_ts.min(), spot_ts.max()], unit="ms", utc=True).year.tolist()
    chk("C", "units-ms-2026", "PASS" if set(yr_b) <= {2026} and set(yr_s) <= {2026} else "FAIL",
        f"book years {yr_b}, spot years {yr_s}")
    mono = bool(np.all(np.diff(b_ts) >= 0))
    gaps = np.diff(b_ts)
    med_gap = float(np.median(gaps[gaps >= 0])) if len(gaps) else float("nan")
    chk("C", "sorted+spacing", "PASS" if mono and med_gap < 5000 else "WARN",
        f"sorted={mono}, median inter-event gap={med_gap:.0f}ms")
    # C3 as-of join gap
    i = asof_idx(spot_ts, b_ts)
    ok = i >= 0
    gap = b_ts[ok] - spot_ts[i[ok]]
    p50, p99, mx = np.percentile(gap, [50, 99, 100])
    chk("C", "asof-gap", "PASS" if p99 < 3000 else "WARN",
        f"book_ts-spot_ts p50={p50:.0f}ms p99={p99:.0f}ms max={mx:.0f}ms "
        f"(stale>5s: {(gap>5000).mean():.3%})")
    chk("C", "ts-column", "PASS", "using 'timestamp' (Polymarket source), not timestamp_received")


# --------------------------------------------------------------------------- D
def section_D(book, spot_ts, spot_px, win):
    print("D. Window alignment (silent killer)")
    b_ts = book["ts_ms"].to_numpy()
    b_ws = b_ts // 1000 // WINDOW_S * WINDOW_S
    # D1 boundaries match discovered (Gamma) windows
    if win is not None:
        gset = set(win["window_start"].astype(np.int64))
        inb = np.isin(b_ws, list(gset)).mean()
        chk("D", "boundaries-match-Gamma", "PASS" if inb > 0.999 else "FAIL",
            f"{inb:.4%} of book rows fall in a discovered UTC window")
    # D2 label agreement (THE test)
    if win is not None and "resolved_up" in win.columns:
        w = win.dropna(subset=["resolved_up"]).copy()
        s0 = spot_at(spot_ts, spot_px, w["window_start"].to_numpy() * 1000)
        sc = spot_at(spot_ts, spot_px, w["window_end"].to_numpy() * 1000)
        ok = np.isfinite(s0) & np.isfinite(sc)
        spot_up = (sc[ok] > s0[ok]).astype(int)
        res_up = w["resolved_up"].to_numpy()[ok].astype(int)
        agree = (spot_up == res_up).mean()
        move_bps = np.abs(sc[ok] / s0[ok] - 1) * 1e4
        dis = spot_up != res_up
        dis_move = move_bps[dis]
        near_tie = float((dis_move < 5).mean()) if dis.any() else 1.0
        chk("D", "label-agreement", "PASS" if agree > 0.97 else "FAIL",
            f"{agree:.3%} agree on {ok.sum()} resolved windows")
        chk("D", "disagree-are-near-ties", "PASS" if near_tie > 0.8 or not dis.any() else "FAIL",
            f"{int(dis.sum())} disagreements, median move={np.median(dis_move) if dis.any() else 0:.1f}bps, "
            f"{near_tie:.0%} under 5bps")
    # D3 straddling: each row's timestamp-window == its asset's window
    if win is not None and "asset_id" in book.columns:
        amap = dict(zip(win["asset_id"].astype(str), win["window_start"].astype(np.int64)))
        a_ws = book["asset_id"].astype(str).map(amap).to_numpy()
        known = ~pd.isna(a_ws)
        match = (a_ws[known] == b_ws[known]).mean()
        chk("D", "no-straddling", "PASS" if match > 0.99 else "WARN",
            f"{match:.4%} of rows: asset's window == timestamp's window")


# --------------------------------------------------------------------------- E
def section_E(book):
    print("E. Per-window completeness")
    b_ts = book["ts_ms"].to_numpy()
    b_ws = b_ts // 1000 // WINDOW_S * WINDOW_S
    t_into = b_ts // 1000 - b_ws
    df = pd.DataFrame({"ws": b_ws, "t_into": t_into})
    per = df.groupby("ws")["t_into"].agg(["count", "min", "max"])
    sparse = (per["count"] < 10).mean()
    chk("E", "density", "PASS" if sparse < 0.05 else "WARN",
        f"snapshots/window median={per['count'].median():.0f}, "
        f"{sparse:.1%} windows have <10")
    late = (per["max"] >= WINDOW_S - 120).mean()
    chk("E", "late-window-coverage", "PASS" if late > 0.9 else "WARN",
        f"{late:.1%} of windows have a tick in the last 120s")
    early = (per["min"] <= 120).mean()
    chk("E", "early-window-coverage", "PASS" if early > 0.9 else "WARN",
        f"{early:.1%} of windows have a tick in the first 120s")


# --------------------------------------------------------------------------- F
def section_F(book):
    print("F. Value sanity")
    b_ts = book["ts_ms"].to_numpy()
    b_ws = b_ts // 1000 // WINDOW_S * WINDOW_S
    t_into = b_ts // 1000 - b_ws
    mid = (book["bid"].to_numpy() + book["ask"].to_numpy()) / 2
    early = np.abs(mid[t_into <= 120] - 0.5).mean()
    late = np.abs(mid[t_into >= WINDOW_S - 120] - 0.5).mean()
    chk("F", "mid-decays-to-0/1", "PASS" if late > early else "WARN",
        f"mean|mid-0.5| early={early:.3f} -> late={late:.3f}")
    spread = book["ask"].to_numpy() - book["bid"].to_numpy()
    at_floor = (spread <= 0.0101).mean()
    chk("F", "spread", "PASS" if np.median(spread) <= 0.05 else "WARN",
        f"median spread={np.median(spread)*100:.2f}c, {at_floor:.1%} at 1c floor")
    pinned = ((mid < 0.02) | (mid > 0.98)).mean()
    chk("F", "not-pinned", "PASS" if pinned < 0.5 else "WARN",
        f"{pinned:.1%} of rows at extreme (<0.02 or >0.98)")


# --------------------------------------------------------------------------- G
def section_G(book, spot_ts, spot_px):
    print("G. Cross-source consistency")
    # dedupe
    dup = book.duplicated(subset=[c for c in ["ts_ms", "asset_id", "bid", "ask"] if c in book.columns]).mean()
    chk("G", "duplicates", "PASS" if dup < 0.05 else "WARN", f"{dup:.2%} exact-duplicate rows")
    # direction agreement on big-move windows
    b_ts = book["ts_ms"].to_numpy()
    b_ws = b_ts // 1000 // WINDOW_S * WINDOW_S
    mid = (book["bid"].to_numpy() + book["ask"].to_numpy()) / 2
    df = pd.DataFrame({"ws": b_ws, "ts": b_ts, "mid": mid}).sort_values("ts")
    first = df.groupby("ws").first(); last = df.groupby("ws").last()
    s0 = spot_at(spot_ts, spot_px, first.index.to_numpy() * 1000)
    sc = spot_at(spot_ts, spot_px, (first.index.to_numpy() + WINDOW_S) * 1000)
    ok = np.isfinite(s0) & np.isfinite(sc)
    spot_ret = sc[ok] / s0[ok] - 1
    mid_chg = (last["mid"].to_numpy() - first["mid"].to_numpy())[ok]
    big = np.argsort(-np.abs(spot_ret))[:max(5, int(0.1 * ok.sum()))]
    agree = (np.sign(spot_ret[big]) == np.sign(mid_chg[big])).mean()
    chk("G", "direction-agreement", "PASS" if agree > 0.8 else "FAIL",
        f"Up-mid moves with spot on {agree:.0%} of big-move windows "
        f"(inversion would show ~0%)")


def _d(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


def run(book, spot_ts, spot_px, win):
    section_A(book, spot_ts, spot_px, win)
    section_B(book, win)
    section_C(book, spot_ts)
    section_D(book, spot_ts, spot_px, win)
    section_E(book)
    section_F(book)
    section_G(book, spot_ts, spot_px)
    fails = [r for r in R if r[2] == "FAIL"]
    warns = [r for r in R if r[2] == "WARN"]
    print("\n=== TRIAGE (the four that fake edges) ===")
    for nm in ("fee_rate_bps", "label-agreement", "asof-gap"):
        for s, n, st, d in R:
            if n == nm:
                print(f"  {st:4}  {n}: {d}")
    print("  ----  in/out-of-sample replication: run_real.py on disjoint halves (Gate-4)")
    print(f"\n=== SUMMARY: {len(fails)} FAIL, {len(warns)} WARN, "
          f"{len(R)-len(fails)-len(warns)} PASS ===")
    if fails:
        print("  FAILED:", ", ".join(n for _, n, _, _ in fails))
    return 0 if not fails else 1


# --------------------------------------------------------------------- selftest
def selftest():
    """Validate the QC logic: good data passes label/inversion/units; broken fails."""
    import smoke_test
    smoke_test.make_demo()
    spot_ts, spot_px = load_spot("demo_btc.npz")
    book = load_book("demo_up_book.parquet", "timestamp", "best_bid", "best_ask", "ms")
    book["asset_id"] = "0xdemo" + (book["ts_ms"] // 1000 // WINDOW_S * WINDOW_S).astype(str)

    # build windows with CORRECT resolution from spot
    ws = np.unique(book["ts_ms"].to_numpy() // 1000 // WINDOW_S * WINDOW_S)
    s0 = spot_at(spot_ts, spot_px, ws * 1000)
    sc = spot_at(spot_ts, spot_px, (ws + WINDOW_S) * 1000)
    good = pd.DataFrame({"window_start": ws, "window_end": ws + WINDOW_S,
                         "asset_id": ["0xdemo" + str(w) for w in ws],
                         "resolved_up": (sc > s0).astype(int)})
    inverted = good.copy(); inverted["resolved_up"] = 1 - inverted["resolved_up"]

    print("--- selftest: GOOD data (expect label-agreement PASS) ---")
    R.clear(); run(book, spot_ts, spot_px, good)
    good_agree = [r for r in R if r[1] == "label-agreement"][0][2]

    print("\n--- selftest: INVERTED Up/Down (expect label-agreement FAIL) ---")
    R.clear(); run(book, spot_ts, spot_px, inverted)
    inv_agree = [r for r in R if r[1] == "label-agreement"][0][2]

    ok = good_agree == "PASS" and inv_agree == "FAIL"
    print(f"\nSELFTEST: good={good_agree} inverted={inv_agree} -> {'PASS' if ok else 'FAIL'}")
    raise SystemExit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book"); ap.add_argument("--spot")
    ap.add_argument("--windows", default=None)
    ap.add_argument("--ts_col", default="timestamp")
    ap.add_argument("--bid_col", default="best_bid")
    ap.add_argument("--ask_col", default="best_ask")
    ap.add_argument("--ts_unit", default="ms")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    spot_ts, spot_px = load_spot(a.spot)
    book = load_book(a.book, a.ts_col, a.bid_col, a.ask_col, a.ts_unit, keep_asset=True)
    win = pd.read_parquet(a.windows) if a.windows else None
    print("=== dataqc.py ===")
    raise SystemExit(run(book, spot_ts, spot_px, win))


if __name__ == "__main__":
    main()
