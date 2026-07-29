#!/usr/bin/env python3
"""spec_D1.py -- FROZEN pre-registered spec D1 (directional SPECs 1/3/7 re-run on genuine
archive n). See venue_expansion/GROUNDING.md, PAPER_TRADER_AUDIT.md, REOPENABLE.md for context,
and the spec text supplied in the task for the frozen rules (reproduced in out/spec_D1.md).

Read-only. Reads local cached markets snapshot (cache/D1/markets_universe.json, pulled from all
4 HF markets shards, exact series_key match on the 8 real KXHIGH city series, close_time window
2024-10-25..2026-01-31) and local cached tape (cache/D1/tape/shard-*.parquet, ALL 16 HF trade
shards, predicate-filtered server-side to the exact ticker universe of that markets pull).

Writes:
  venue_expansion/out/spec_D1.json  -- full records + summary
  venue_expansion/out/spec_D1.md    -- method + results + skip ledger
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics as st
import sys
import time
from datetime import datetime, timedelta, timezone

import duckdb
from scipy import stats as sstats
from scipy.optimize import isotonic_regression

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "D1")
TAPE_DIR = os.path.join(CACHE, "tape")
OUT_JSON = os.path.join(HERE, "out", "spec_D1.json")
OUT_MD = os.path.join(HERE, "out", "spec_D1.md")

SERIES = ["KXHIGHNY", "KXHIGHCHI", "KXHIGHAUS", "KXHIGHMIA",
          "KXHIGHDEN", "KXHIGHPHIL", "KXHIGHLAX", "KXHIGHHOU"]
WINDOW_START = "2024-10-25"
WINDOW_END = "2026-01-31"
TAPE_END = datetime(2026, 1, 28, tzinfo=timezone.utc)  # archive truncation, informational

SUF_RE = re.compile(r'^([A-Z])(-?\d+\.?\d*)$')

H_LOOKBACK = timedelta(minutes=30)          # p_ask window: [H-30m, H]
SPREAD_WIN = timedelta(minutes=30)          # effective-spread bid window: [H-30m, H+30m]
ENTRY_WIN = timedelta(minutes=15)           # entry window: [H, H+15m]
VOL24 = timedelta(hours=24)                 # SPEC3 thin-book lookback

ALPHA_LEG = 0.0125 / 3  # 0.0041667, D1's 3-way internal Bonferroni split

SKIP_LOG = {"SPEC1": [], "SPEC3": [], "SPEC7": []}


def skip(leg, key, reason, extra=None):
    rec = {"key": key, "reason": reason}
    if extra:
        rec["extra"] = extra
    SKIP_LOG[leg].append(rec)


def parse_dt(s):
    if isinstance(s, datetime):
        return s
    s = str(s)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fee_cents(p):
    """Kalshi taker fee, ceil(7*p*(1-p)) CENTS, p = the leg's own transacted price in [0,1]."""
    p = max(0.0, min(1.0, p))
    return math.ceil(7 * p * (1 - p))


def day_clustered_t(cluster_means):
    n = len(cluster_means)
    if n < 2:
        return (cluster_means[0] if n == 1 else None), None, n
    m = st.mean(cluster_means)
    sd = st.stdev(cluster_means)
    se = sd / math.sqrt(n)
    t = (m / se) if se > 0 else (float("inf") if m > 0 else (float("-inf") if m < 0 else 0.0))
    return m, t, n


def wilson_lb(k, n, z=1.959963984540054):
    if n == 0:
        return None
    phat = k / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    adj = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return (center - adj) / denom


def t_crit(alpha_two_sided, df):
    return float(sstats.t.ppf(1 - alpha_two_sided / 2, df))


def fit_isotonic(pairs):
    """pairs: list of (x, y) with x=p_ask in [0,1], y in {0,1}. Returns predict(x) fn, PAVA fit
    on TRAIN sorted by x, ties pooled, linear interpolation between fitted training points,
    clipped at the boundary values outside the TRAIN x-range (out-of-bounds clip, never refit)."""
    if len(pairs) < 2:
        return None
    pairs_sorted = sorted(pairs, key=lambda p: p[0])
    xs = [p[0] for p in pairs_sorted]
    ys = [p[1] for p in pairs_sorted]
    fitted = isotonic_regression(ys, increasing=True).x
    # collapse to unique x for interpolation (PAVA already gives equal fitted value within tie blocks)
    uniq_x, uniq_y = [], []
    for x, y in zip(xs, fitted):
        if uniq_x and x == uniq_x[-1]:
            continue
        uniq_x.append(x)
        uniq_y.append(y)

    def predict(x):
        if x <= uniq_x[0]:
            return uniq_y[0]
        if x >= uniq_x[-1]:
            return uniq_y[-1]
        # linear interpolation
        lo_i = 0
        hi_i = len(uniq_x) - 1
        # simple scan (n is small: TRAIN-B-rung count)
        for i in range(len(uniq_x) - 1):
            if uniq_x[i] <= x <= uniq_x[i + 1]:
                lo_i, hi_i = i, i + 1
                break
        x0, x1 = uniq_x[lo_i], uniq_x[hi_i]
        y0, y1 = uniq_y[lo_i], uniq_y[hi_i]
        if x1 == x0:
            return y0
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    return predict


def main():
    t_start = time.time()
    log_lines = []

    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    # ---------- load markets universe ----------
    uni = json.load(open(os.path.join(CACHE, "markets_universe.json")))
    cols = uni["cols"]
    idx = {c: i for i, c in enumerate(cols)}
    rows = uni["rows"]
    log(f"markets_universe: {len(rows)} rows loaded (8 series, window {WINDOW_START}..{WINDOW_END})")

    rungs = []
    n_unparseable = 0
    for r in rows:
        tk = r[idx["ticker"]]
        ev = r[idx["event_ticker"]]
        sk = r[idx["series_key"]]
        suffix = tk[len(ev) + 1:]
        m = SUF_RE.match(suffix)
        if not m or m.group(1) not in ("B", "T"):
            skip("SPEC1", tk, "strike unparseable")
            skip("SPEC3", tk, "strike unparseable")
            skip("SPEC7", tk, "strike unparseable")
            n_unparseable += 1
            continue
        letter = m.group(1)
        num = float(m.group(2))
        close_time = parse_dt(r[idx["close_time"]])
        h = close_time - timedelta(hours=2)
        rungs.append({
            "ticker": tk, "event_ticker": ev, "city": sk,
            "rung_class": letter, "strike": num,
            "lo": (num - 0.5) if letter == "B" else None,
            "hi": (num + 0.5) if letter == "B" else None,
            "close_time": close_time, "h": h,
            "h_lo": h - H_LOOKBACK, "h_hi_spread": h + SPREAD_WIN, "h_lo_spread": h - SPREAD_WIN,
            "entry_hi": h + ENTRY_WIN, "vol24_lo": h - VOL24,
            "settle_date": close_time.date().isoformat(),
            "result": r[idx["result"]],
        })
    log(f"parsed rungs: {len(rungs)}  (unparseable tickers dropped: {n_unparseable})")

    # ---------- per-event settlement status (all-or-nothing, verified on this pull) ----------
    by_event = {}
    for rg in rungs:
        by_event.setdefault(rg["event_ticker"], []).append(rg)
    event_settled = {}
    for ev, rs in by_event.items():
        settled_flags = [rg["result"] in ("yes", "no") for rg in rs]
        event_settled[ev] = all(settled_flags) and len(settled_flags) > 0
        if any(settled_flags) and not all(settled_flags):
            log(f"WARNING partial settlement in event {ev} -- unexpected, treating as unsettled")
            event_settled[ev] = False

    # ---------- per-city TRAIN/TEST split on distinct SETTLED settlement dates ----------
    city_dates = {c: sorted({rg["settle_date"] for rg in rungs
                              if rg["city"] == c and event_settled[rg["event_ticker"]]})
                  for c in SERIES}
    city_split = {}
    for c, dates in city_dates.items():
        n = len(dates)
        cut = int(round(n * 0.6))
        train_dates = set(dates[:cut])
        test_dates = set(dates[cut:])
        city_split[c] = (train_dates, test_dates)
        log(f"  {c:<12s} settled_dates={n:>4d}  TRAIN={len(train_dates):>4d}  TEST={len(test_dates):>4d}")

    def split_of(rg):
        if not event_settled[rg["event_ticker"]]:
            return None
        tr, te = city_split[rg["city"]]
        if rg["settle_date"] in tr:
            return "TRAIN"
        if rg["settle_date"] in te:
            return "TEST"
        return None

    for rg in rungs:
        rg["split"] = split_of(rg)

    # events with no settlement at all are excluded from TRAIN/TEST by construction (the split is
    # defined over SETTLED dates) -- log them explicitly per non-negotiable 7 rather than letting
    # them vanish silently, attributed to whichever leg their rung_class would have made them
    # eligible for.
    n_unsettled_events = sum(1 for v in event_settled.values() if not v)
    for rg in rungs:
        if not event_settled[rg["event_ticker"]]:
            if rg["rung_class"] == "B":
                skip("SPEC1", rg["ticker"], "result unavailable")
                skip("SPEC3", rg["ticker"], "result unavailable")
            else:
                skip("SPEC7", rg["ticker"], "result unavailable")
    log(f"events with no settlement at all (excluded from TRAIN/TEST entirely, logged): {n_unsettled_events}")

    # ---------- load tape: ALL 16 shards, assert count ----------
    shard_re = re.compile(r'^shard-\d{4}\.parquet$')
    shard_files = sorted(os.path.join(TAPE_DIR, f) for f in os.listdir(TAPE_DIR) if shard_re.match(f))
    assert len(shard_files) == 16, f"expected 16 cached shards, found {len(shard_files)}: {shard_files}"
    con = duckdb.connect()
    tape_src = "read_parquet([" + ",".join(f"'{p}'" for p in shard_files) + "])"
    n_trades, n_tickers, tmin, tmax = con.execute(
        f"SELECT count(*), count(DISTINCT ticker), min(created_time), max(created_time) FROM {tape_src}"
    ).fetchone()
    log(f"local tape (ALL 16 shards): {n_trades} trades, {n_tickers} distinct tickers, {tmin} .. {tmax}")
    con.execute(f"CREATE TEMP TABLE tape AS SELECT ticker, count, yes_price, no_price, taker_side, "
                f"created_time FROM {tape_src}")
    con.execute("CREATE INDEX idx_tape_ticker ON tape(ticker)")

    # ---------- push rungs into duckdb for bulk ASOF joins ----------
    con.execute("""
        CREATE TEMP TABLE rungs(
            ticker VARCHAR, event_ticker VARCHAR, city VARCHAR, rung_class VARCHAR,
            strike DOUBLE, lo DOUBLE, hi DOUBLE,
            h TIMESTAMP, h_lo TIMESTAMP, h_lo_spread TIMESTAMP, h_hi_spread TIMESTAMP,
            entry_hi TIMESTAMP, vol24_lo TIMESTAMP, settle_date VARCHAR, split VARCHAR, result VARCHAR
        )
    """)
    con.executemany(
        "INSERT INTO rungs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(rg["ticker"], rg["event_ticker"], rg["city"], rg["rung_class"], rg["strike"], rg["lo"], rg["hi"],
          rg["h"], rg["h_lo"], rg["h_lo_spread"], rg["h_hi_spread"], rg["entry_hi"], rg["vol24_lo"],
          rg["settle_date"], rg["split"], rg["result"]) for rg in rungs])
    con.execute("CREATE INDEX idx_rungs_ticker ON rungs(ticker)")

    # p_ask_signal: last taker='yes' print in [h_lo, h]  (backward asof, then filter lower bound)
    log("\ncomputing bulk signal quantities (ASOF joins over full local tape)...")
    p_ask_rows = con.execute("""
        SELECT r.ticker, t.yes_price, t.created_time
        FROM rungs r
        ASOF LEFT JOIN tape t ON r.ticker = t.ticker AND t.created_time <= r.h AND t.taker_side='yes'
        WHERE t.created_time IS NULL OR t.created_time >= r.h_lo
    """).fetchall()
    p_ask = {}
    for tkr, yp, ct in p_ask_rows:
        if yp is not None:
            p_ask[tkr] = (yp / 100.0, ct)

    # p_bid_signal (SPEC3 symmetric leg trigger source): last taker='no' print in [h_lo, h]
    p_bid_rows = con.execute("""
        SELECT r.ticker, t.no_price, t.created_time
        FROM rungs r
        ASOF LEFT JOIN tape t ON r.ticker = t.ticker AND t.created_time <= r.h AND t.taker_side='no'
        WHERE t.created_time IS NULL OR t.created_time >= r.h_lo
    """).fetchall()
    p_bid = {}
    for tkr, np_, ct in p_bid_rows:
        if np_ is not None:
            p_bid[tkr] = ((100 - np_) / 100.0, ct)

    # SPEC1 effective-spread: nearest taker='no' print within [h_lo_spread, h_hi_spread]
    spread_bid_rows = con.execute("""
        SELECT ticker, no_price, created_time FROM (
            SELECT r.ticker, t.no_price, t.created_time,
                   abs(epoch(t.created_time) - epoch(r.h)) AS dist,
                   row_number() OVER (PARTITION BY r.ticker ORDER BY abs(epoch(t.created_time)-epoch(r.h))) AS rn
            FROM rungs r
            JOIN tape t ON r.ticker = t.ticker AND t.taker_side='no'
                AND t.created_time >= r.h_lo_spread AND t.created_time <= r.h_hi_spread
        ) WHERE rn = 1
    """).fetchall()
    spread_bid = {tkr: ((100 - np_) / 100.0, ct) for tkr, np_, ct in spread_bid_rows}

    # SPEC7 "last print at/before H, any side" in [h_lo, h]
    last_any_rows = con.execute("""
        SELECT r.ticker, t.taker_side, t.yes_price, t.no_price, t.created_time
        FROM rungs r
        ASOF LEFT JOIN tape t ON r.ticker = t.ticker AND t.created_time <= r.h
        WHERE t.created_time IS NULL OR t.created_time >= r.h_lo
    """).fetchall()
    last_any = {}
    for tkr, side, yp, np_, ct in last_any_rows:
        if side is None:
            continue
        yeq = (yp / 100.0) if side == "yes" else ((100 - np_) / 100.0)
        last_any[tkr] = (yeq, ct)

    # entry: first taker='no' print in [h, entry_hi]  (forward asof)
    entry_no_rows = con.execute("""
        SELECT r.ticker, t.no_price, t.created_time, t.count
        FROM rungs r
        ASOF LEFT JOIN tape t ON r.ticker = t.ticker AND t.created_time >= r.h AND t.taker_side='no'
        WHERE t.created_time IS NULL OR t.created_time <= r.entry_hi
    """).fetchall()
    entry_no = {}
    for tkr, np_, ct, cnt in entry_no_rows:
        if np_ is not None:
            entry_no[tkr] = (np_, ct, cnt)

    # entry: first taker='yes' print in [h, entry_hi]  (forward asof)
    entry_yes_rows = con.execute("""
        SELECT r.ticker, t.yes_price, t.created_time, t.count
        FROM rungs r
        ASOF LEFT JOIN tape t ON r.ticker = t.ticker AND t.created_time >= r.h AND t.taker_side='yes'
        WHERE t.created_time IS NULL OR t.created_time <= r.entry_hi
    """).fetchall()
    entry_yes = {}
    for tkr, yp, ct, cnt in entry_yes_rows:
        if yp is not None:
            entry_yes[tkr] = (yp, ct, cnt)

    # 24h pre-H traded volume, B rungs only (SPEC3 thin-book tercile)
    vol24_rows = con.execute("""
        SELECT r.ticker, coalesce(sum(t.count), 0)
        FROM rungs r
        LEFT JOIN tape t ON r.ticker = t.ticker AND t.created_time >= r.vol24_lo AND t.created_time <= r.h
        WHERE r.rung_class = 'B'
        GROUP BY r.ticker
    """).fetchall()
    vol24 = {tkr: v for tkr, v in vol24_rows}

    log(f"signal quantities computed: p_ask={len(p_ask)} p_bid={len(p_bid)} spread_bid={len(spread_bid)} "
        f"last_any={len(last_any)} entry_no={len(entry_no)} entry_yes={len(entry_yes)} vol24={len(vol24)}")

    rg_by_ticker = {rg["ticker"]: rg for rg in rungs}

    # =========================================================================================
    # SPEC 1 -- horizon-conditional calibration fade, rung_class='B'
    # =========================================================================================
    log("\n=== SPEC 1 ===")
    b_rungs = [rg for rg in rungs if rg["rung_class"] == "B"]

    # ---- FIT: isotonic map on TRAIN, pooled across all 8 cities, (p_ask, outcome) pairs ----
    train_pairs = []
    train_pairs_dropped = 0
    for rg in b_rungs:
        if rg["split"] != "TRAIN":
            continue
        pa = p_ask.get(rg["ticker"])
        if pa is None:
            train_pairs_dropped += 1
            continue
        outcome = 1.0 if rg["result"] == "yes" else 0.0
        train_pairs.append((pa[0], outcome))
    log(f"SPEC1 isotonic FIT sample: {len(train_pairs)} TRAIN (p_ask,outcome) pairs "
        f"({train_pairs_dropped} TRAIN B-rungs had no ask print in [H-30m,H], excluded from the fit)")
    iso_predict = fit_isotonic(train_pairs)
    if iso_predict is None:
        result1 = {"verdict": "INSUFFICIENT",
                   "verdict_reason": "isotonic FIT sample < 2 -- calibration map cannot be fit."}
    else:
        # ---- TEST: apply frozen trigger, construct trades ----
        spec1_trades = []
        for rg in b_rungs:
            if rg["split"] != "TEST":
                continue
            tk = rg["ticker"]
            pa = p_ask.get(tk)
            if pa is None:
                skip("SPEC1", tk, "no ask print in [H-30m,H]")
                continue
            p_ask_val, _ = pa
            sb = spread_bid.get(tk)
            if sb is None:
                skip("SPEC1", tk, "no bid print for the effective-spread check")
                continue
            bid_val, _ = sb
            eff_spread = p_ask_val - bid_val
            if eff_spread > 0.10:
                skip("SPEC1", tk, "effective spread > 0.10", {"spread": eff_spread})
                continue
            if p_ask_val < 0.85:
                continue  # does not trigger, not a logged skip
            cal = iso_predict(p_ask_val)
            if (p_ask_val - cal) < 0.02:
                continue  # does not trigger
            if rg["result"] not in ("yes", "no"):
                skip("SPEC1", tk, "result unavailable")
                continue
            en = entry_no.get(tk)
            if en is None:
                skip("SPEC1", tk, "no matching-side print within 15min of signal", {"side": "no"})
                continue
            no_price_c, ectime, ecount = en
            fee_c = fee_cents(no_price_c / 100.0)
            won = 1.0 if rg["result"] == "no" else 0.0
            net_c = won * 100.0 - no_price_c - fee_c
            spec1_trades.append({
                "ticker": tk, "city": rg["city"], "settle_date": rg["settle_date"],
                "p_ask": p_ask_val, "iso_cal": cal, "eff_spread": eff_spread,
                "entry_price_c": no_price_c, "entry_count": ecount,
                "entry_time": str(ectime), "fee_c": fee_c, "result": rg["result"], "net_c": net_c,
            })
        log(f"SPEC1 TEST qualifying trades (triggered + entry executed): {len(spec1_trades)}")
        result1 = evaluate_leg("SPEC1", spec1_trades, min_entries=200, min_dates=40, log=log)
        result1["isotonic_fit_n"] = len(train_pairs)

    # =========================================================================================
    # SPEC 3 -- thin-book longshot fade, rung_class='B'
    # =========================================================================================
    log("\n=== SPEC 3 ===")
    # bottom-volume-tercile membership computed PER LADDER (event_ticker), among that event's B rungs
    ladder_b = {}
    for rg in b_rungs:
        ladder_b.setdefault(rg["event_ticker"], []).append(rg)
    bottom_tercile = set()  # tickers
    for ev, rs in ladder_b.items():
        if len(rs) < 3:
            continue  # tercile undefined for <3 rungs; those rungs simply never qualify (not a logged skip)
        vols = sorted(((vol24.get(rg["ticker"], 0), rg["ticker"]) for rg in rs), key=lambda x: x[0])
        cutoff_idx = max(1, len(vols) // 3)
        for v, tk in vols[:cutoff_idx]:
            bottom_tercile.add(tk)
    log(f"SPEC3 bottom-tercile rung count (across all B ladders, TRAIN+TEST): {len(bottom_tercile)}")

    spec3_trades = []
    for rg in b_rungs:
        if rg["split"] != "TEST":
            continue
        tk = rg["ticker"]
        if tk not in bottom_tercile:
            continue  # not a logged skip -- simply not in the eligible population
        pa = p_ask.get(tk)
        pb = p_bid.get(tk)
        side = None
        if pa is not None and pa[0] >= 0.85:
            side = "no"
            trig_price = pa[0]
        elif pb is not None and pb[0] <= 0.15:
            side = "yes"
            trig_price = pb[0]
        if side is None:
            continue  # neither leg triggers -- not logged
        if rg["result"] not in ("yes", "no"):
            skip("SPEC3", tk, "result unavailable")
            continue
        if side == "no":
            en = entry_no.get(tk)
            if en is None:
                skip("SPEC3", tk, "no matching-side print within 15min of signal", {"side": "no"})
                continue
            price_c, ectime, ecount = en
            won = 1.0 if rg["result"] == "no" else 0.0
        else:
            en = entry_yes.get(tk)
            if en is None:
                skip("SPEC3", tk, "no matching-side print within 15min of signal", {"side": "yes"})
                continue
            price_c, ectime, ecount = en
            won = 1.0 if rg["result"] == "yes" else 0.0
        fee_c = fee_cents(price_c / 100.0)
        net_c = won * 100.0 - price_c - fee_c
        spec3_trades.append({
            "ticker": tk, "city": rg["city"], "settle_date": rg["settle_date"], "side": side,
            "trigger_price": trig_price, "entry_price_c": price_c, "entry_count": ecount,
            "entry_time": str(ectime), "fee_c": fee_c, "result": rg["result"], "net_c": net_c,
        })
    log(f"SPEC3 TEST qualifying trades (triggered + entry executed): {len(spec3_trades)}")
    result3 = evaluate_leg("SPEC3", spec3_trades, min_entries=300, min_dates=None, log=log)

    # =========================================================================================
    # SPEC 7 -- salient-threshold anchoring bias, rung_class='T'  (not a t-test)
    # =========================================================================================
    log("\n=== SPEC 7 ===")
    t_rungs = [rg for rg in rungs if rg["rung_class"] == "T"]
    BINS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0001)]

    def bin_of(p):
        for i, (lo, hi) in enumerate(BINS):
            if lo <= p < hi:
                return i
        return None

    def build_spec7_obs(split_name):
        obs = []
        drop_ct = {"no print in [H-30m,H] (SPEC7 price)": 0, "result unavailable": 0}
        for rg in t_rungs:
            if rg["split"] != split_name:
                continue
            tk = rg["ticker"]
            la = last_any.get(tk)
            if la is None:
                drop_ct["no print in [H-30m,H] (SPEC7 price)"] += 1
                continue
            price, _ = la
            if rg["result"] not in ("yes", "no"):
                drop_ct["result unavailable"] += 1
                continue
            outcome = 1.0 if rg["result"] == "yes" else 0.0
            salient = (int(rg["strike"]) % 10 == 0)
            b = bin_of(price)
            if b is None:
                continue
            obs.append({"ticker": tk, "price": price, "outcome": outcome, "gap": price - outcome,
                        "salient": salient, "bin": b})
        return obs, drop_ct

    def bin_eligibility(obs):
        cells = {}
        for o in obs:
            cells.setdefault((o["bin"], o["salient"]), []).append(o["gap"])
        elig = []
        detail = {}
        for b in range(5):
            n_sal = len(cells.get((b, True), []))
            n_non = len(cells.get((b, False), []))
            ok = n_sal >= 20 and n_non >= 20
            gap = None
            if ok:
                gap = st.mean(cells[(b, True)]) - st.mean(cells[(b, False)])
            detail[b] = {"n_salient": n_sal, "n_nonsalient": n_non, "eligible": ok, "gap": gap}
            if ok:
                elig.append(b)
        return elig, detail

    train_obs, train_drop = build_spec7_obs("TRAIN")
    train_elig, train_detail = bin_eligibility(train_obs)
    log(f"SPEC7 TRAIN: n_obs={len(train_obs)} drop={train_drop} eligible_bins={train_elig} detail={train_detail}")

    if len(train_elig) < 3:
        result7 = {
            "verdict": "INSUFFICIENT",
            "verdict_reason": f"TRAIN self-kill: only {len(train_elig)}/5 price bins reached "
                               f"MIN_GROUP_N=20 per (bin,salience) cell on TRAIN -- reproduces the original "
                               f"kill mode. TEST not opened (kill_conditions / non-negotiable 1: never open "
                               f"validation after a self-kill).",
            "train_n_obs": len(train_obs), "train_drop": train_drop,
            "train_bin_detail": train_detail, "train_eligible_bins": train_elig,
        }
        log("SPEC7 SELF-KILL on TRAIN. TEST not opened.")
    else:
        test_obs, test_drop = build_spec7_obs("TEST")
        test_elig, test_detail = bin_eligibility(test_obs)
        log(f"SPEC7 TEST: n_obs={len(test_obs)} drop={test_drop} eligible_bins={test_elig} detail={test_detail}")
        for b, d in test_detail.items():
            if not d["eligible"]:
                skip("SPEC7", f"bin{b}", "bin ineligible on TEST (MIN_GROUP_N=20 unmet in a (bin,salience) cell)",
                     d)
        big_gap_bins = [b for b in test_elig if test_detail[b]["gap"] is not None
                        and abs(test_detail[b]["gap"]) >= 0.04]
        signs = set()
        for b in big_gap_bins:
            g = test_detail[b]["gap"]
            signs.add(1 if g > 0 else -1)
        sign_agree = len(signs) == 1
        n_elig = len(test_elig)
        pass7 = (n_elig >= 3) and (len(big_gap_bins) >= 3) and sign_agree
        result7 = {
            "verdict": "PASS" if pass7 else "FAIL",
            "train_n_obs": len(train_obs), "train_drop": train_drop,
            "train_bin_detail": train_detail, "train_eligible_bins": train_elig,
            "test_n_obs": len(test_obs), "test_drop": test_drop,
            "test_bin_detail": test_detail, "test_eligible_bins": test_elig,
            "big_gap_bins (|gap|>=0.04)": big_gap_bins, "sign_agreement": sign_agree,
        }
        if not pass7:
            reasons = []
            if n_elig < 3:
                reasons.append(f"only {n_elig}/5 bins eligible on TEST (need >=3)")
            if len(big_gap_bins) < 3:
                reasons.append(f"only {len(big_gap_bins)}/5 bins have |gap|>=0.04 (need >=3)")
            if not sign_agree:
                reasons.append(f"sign disagreement among big-gap bins: {[test_detail[b]['gap'] for b in big_gap_bins]}")
            result7["verdict_reason"] = "; ".join(reasons)
        log(f"SPEC7 VERDICT: {result7['verdict']}  ({result7.get('verdict_reason','')})")

    # =========================================================================================
    # assemble + write
    # =========================================================================================
    overall_pass = any(r.get("verdict") == "PASS" for r in (result1, result3, result7))
    result = {
        "spec_id": "D1",
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "window": [WINDOW_START, WINDOW_END], "tape_archive_end": TAPE_END.isoformat(),
        "series": SERIES,
        "shards_read": "all 16 trade shards + all 4 markets shards",
        "n_trades_local_tape": n_trades, "n_tickers_local_tape": n_tickers,
        "tape_span": [str(tmin), str(tmax)],
        "n_rungs_total": len(rungs), "n_unparseable": n_unparseable,
        "n_b_rungs": len(b_rungs), "n_t_rungs": len(t_rungs),
        "city_settled_dates": {c: len(city_dates[c]) for c in SERIES},
        "city_split": {c: {"train": len(city_split[c][0]), "test": len(city_split[c][1])} for c in SERIES},
        "alpha_per_leg": ALPHA_LEG,
        "SPEC1": result1, "SPEC3": result3, "SPEC7": result7,
        "verdict": "PASS" if overall_pass else (
            "INSUFFICIENT" if all(r.get("verdict") == "INSUFFICIENT" for r in (result1, result3, result7))
            else "FAIL" if all(r.get("verdict") in ("FAIL", "INSUFFICIENT") for r in (result1, result3, result7))
            else "NULL"),
        "skip_ledger": SKIP_LOG,
        "runtime_sec": time.time() - t_start,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(result, open(OUT_JSON, "w"), indent=1, default=str)
    print(f"\nwrote {OUT_JSON}")
    write_md(result, log_lines)
    print(f"wrote {OUT_MD}")


def evaluate_leg(leg, trades, min_entries, min_dates, log):
    """Common SPEC1/SPEC3 pass-bar evaluator: EV clauses, day-clustered t (calendar-date
    clustering, pooled across cities), Wilson CI, drop-5-best-dates, per-city sign check."""
    n = len(trades)
    dates_present = sorted(set(tr["settle_date"] for tr in trades))
    n_dates = len(dates_present)
    if n < min_entries or (min_dates is not None and n_dates < min_dates):
        reason = f"n={n} (need >={min_entries})"
        if min_dates is not None:
            reason += f", n_dates={n_dates} (need >={min_dates})"
        return {"verdict": "INSUFFICIENT", "verdict_reason": f"min_n gate failed: {reason}.",
                "n_qualifying": n, "n_dates": n_dates, "trades": trades}

    byday = {}
    for tr in trades:
        byday.setdefault(tr["settle_date"], []).append(tr)
    print_weighted_mean = st.mean(tr["net_c"] for tr in trades)
    total_contracts = sum(tr["entry_count"] for tr in trades)
    contract_weighted_mean = sum(tr["net_c"] * tr["entry_count"] for tr in trades) / total_contracts

    cluster_means = [st.mean(t["net_c"] for t in v) for v in byday.values()]
    mean_c, t_stat, ncl = day_clustered_t(cluster_means)
    df = ncl - 1
    bar = t_crit(ALPHA_LEG, df)

    day_mean_pairs = sorted(byday.items(), key=lambda kv: -st.mean(t["net_c"] for t in kv[1]))
    dropped_days = set(k for k, _ in day_mean_pairs[:5])
    remaining = [tr for tr in trades if tr["settle_date"] not in dropped_days]
    robust_mean = st.mean(tr["net_c"] for tr in remaining) if remaining else None

    wins = sum(1 for tr in trades if tr["net_c"] > 0)
    wlb = wilson_lb(wins, n)
    mean_entry_price = st.mean(tr["entry_price_c"] for tr in trades) / 100.0
    mean_entry_fee = st.mean(tr["fee_c"] for tr in trades) / 100.0
    breakeven = mean_entry_price + mean_entry_fee

    by_city = {}
    for tr in trades:
        by_city.setdefault(tr["city"], []).append(tr["net_c"])
    city_stats = {c: {"n": len(v), "mean_net_c": st.mean(v)} for c, v in by_city.items()}
    qualifying_cities = {c: v for c, v in city_stats.items() if v["n"] >= 25}
    overall_sign = 1 if mean_c > 0 else (-1 if mean_c < 0 else 0)
    sign_match = sum(1 for v in qualifying_cities.values()
                      if (1 if v["mean_net_c"] > 0 else (-1 if v["mean_net_c"] < 0 else 0)) == overall_sign)

    clause1 = (contract_weighted_mean >= 0.50) and (print_weighted_mean >= 0.50)
    clause2 = (t_stat is not None) and (t_stat >= bar)
    clause3 = (wlb is not None) and (wlb > breakeven)
    clause4 = (robust_mean is not None) and (robust_mean > 0)
    clause5 = sign_match >= 6

    all_pass = clause1 and clause2 and clause3 and clause4 and clause5
    res = {
        "verdict": "PASS" if all_pass else "FAIL",
        "n_qualifying": n, "n_dates": ncl,
        "print_weighted_mean_c": print_weighted_mean, "contract_weighted_mean_c": contract_weighted_mean,
        "day_clustered_t": t_stat, "df": df, "t_bar_exact": bar,
        "dropped_5_best_dates": sorted(dropped_days), "robust_mean_after_drop5_c": robust_mean,
        "wins": wins, "n_for_wilson": n, "wilson_lb": wlb,
        "mean_entry_price_dollars": mean_entry_price, "mean_entry_fee_dollars": mean_entry_fee,
        "breakeven_win_rate": breakeven,
        "city_stats": city_stats, "qualifying_cities_ge25": list(qualifying_cities.keys()),
        "overall_sign": overall_sign, "city_sign_match_count": sign_match,
        "clauses": {
            "1_mean_ev_both_weightings_ge_0.50c": clause1,
            "2_day_clustered_t_ge_bar": clause2,
            "3_wilson_lb_above_breakeven": clause3,
            "4_robust_after_drop5": clause4,
            "5_sign_6of8_cities_ge25": clause5,
        },
        "trades": trades,
    }
    if not all_pass:
        res["verdict_reason"] = f"pass-bar clauses failed: {[k for k,v in res['clauses'].items() if not v]}"
    log(f"{leg}: n={n} dates={ncl} print_w_mean={print_weighted_mean:.4f}c contract_w_mean={contract_weighted_mean:.4f}c "
        f"t={t_stat} bar={bar:.4f} clauses={res['clauses']}")
    return res


def write_md(r, log_lines):
    lines = []
    lines.append("# spec_D1 -- directional SPECs 1/3/7 re-run at archive n")
    lines.append("")
    lines.append(f"Run: {r['run_ts']}")
    lines.append("")
    lines.append("## Data")
    lines.append(f"- Series (exact series_key match, NOT a `KXHIGH%` prefix): {r['series']}")
    lines.append(f"- Window: close_time in [{r['window'][0]}, {r['window'][1]}]; trade archive is separately "
                 f"truncated at {r['tape_archive_end'][:10]} (verified archive coverage ceiling) -- signals whose "
                 "H falls after that date, or whose [H-30m,H+15m] windows run past it, show up as legitimate "
                 "print-not-found skips below, not as a silent gap.")
    lines.append(f"- Shards read: **{r['shards_read']}** (16 trade shards is the full archive per DATA_SOURCES.md; "
                 "the repo's kx_history.py N_TRADE_SHARDS=9 bug was NOT used here).")
    lines.append(f"- Local cached tape: {r['n_trades_local_tape']} trades, {r['n_tickers_local_tape']} distinct "
                 f"tickers, span {r['tape_span'][0]} .. {r['tape_span'][1]}")
    lines.append(f"- Rungs parsed: {r['n_rungs_total']} ({r['n_b_rungs']} bracket 'B', {r['n_t_rungs']} threshold "
                 f"'T'; {r['n_unparseable']} unparseable ticker suffixes, logged).")
    lines.append("- Outcomes: Kalshi's own `result` field in the archived markets table -- Kalshi's official "
                 "settled outcome (GROUNDING.md, DATA_SOURCES.md). No bracket/threshold outcome was re-derived; "
                 "settlement is read, never computed, per PAPER_TRADER_AUDIT.md's off-by-one finding. Live "
                 "reconciliation via GET /trade-api/v2/markets/{ticker} was not attempted for archived-era "
                 "tickers -- M1's run already established that every archived-era ticker 404s on the live "
                 "endpoint (the live/historical retention wall), so it would add nothing; noted here for the "
                 "record rather than silently skipped.")
    lines.append("- Executable prices: yes-equivalent ASK from a `taker_side='yes'` print (`yes_price/100`, the "
                 "price a YES buyer actually paid); yes-equivalent BID from a `taker_side='no'` print "
                 "(`(100-no_price)/100`, since buying NO at `no_price` is the mechanical complement of selling "
                 "YES). Entry price for OUR OWN side is always that print's own transacted price -- `no_price/100` "
                 "when we buy NO, `yes_price/100` when we buy YES -- never a mid, never best-in-window.")
    lines.append(f"- TRAIN/TEST split: chronological first 60% / last 40% of distinct SETTLED settlement dates, "
                 "computed INDEPENDENTLY PER CITY (their date ranges differ; KXHIGHHOU has only 70 settled dates "
                 "total vs ~459 for the four earliest cities).")
    lines.append("")
    lines.append("| city | settled dates | TRAIN | TEST |")
    lines.append("|---|---:|---:|---:|")
    for c in r["series"]:
        lines.append(f"| {c} | {r['city_settled_dates'][c]} | {r['city_split'][c]['train']} | {r['city_split'][c]['test']} |")
    lines.append("")
    lines.append(f"D1 splits its funnel share alpha=0.0125 three ways internally: alpha_per_leg = "
                 f"0.0125/3 = {r['alpha_per_leg']:.7f} two-sided, exact t quantile at each leg's own "
                 "day-clustered df (never the z-normal limit).")
    lines.append("")
    lines.append("## Interpretive constructions required by the frozen spec text (documented, not bar-moving)")
    lines.append("1. **SPEC 1 is single-legged, as literally written.** SPEC 1's entry_rule states one trigger "
                 "condition (`p_ask>=0.85` AND miscalibration `>=0.02`), which only fades an overpriced high ask "
                 "by buying NO. The entry_rule's 'symmetric low leg buys YES' sentence appears directly after "
                 "SPEC 3's own explicit two-sided trigger (`p_ask>=0.85` OR `bid<=0.15`) and is read here as "
                 "describing SPEC 3's mechanics, not as adding an unstated low-side trigger to SPEC 1 -- inventing "
                 "one would itself be substituting a new spec for the original text (an AUTO-REFUTE condition).")
    lines.append("2. **Isotonic map is pooled across all 8 cities**, fit once on all TRAIN B-rung (p_ask, outcome) "
                 "pairs (not per-city) -- the spec names one calibration map per horizon H, not eight.")
    lines.append("3. **Effective-spread bid print uses the ±30-minute window verbatim** and picks the print "
                 "*nearest in time to H* among taker='no' prints in that window (not 'last before H', since the "
                 "re-specification text explicitly says 'within ±30 minutes', a window centered on H, distinct "
                 "from p_ask's own '[H-30m,H]' lookback-only window).")
    lines.append("4. **SPEC 7's 'executable yes-equivalent price'** is defined as the yes-equivalent price of the "
                 "single most recent transacted print (either side) at or before H, inside [H-30m,H] -- reusing "
                 "the same 30-minute lookback convention as SPEC 1/3's ask window, and always an actual crossing "
                 "print, never a mid. SPEC 7's own H is the same close_time-2h convention as SPEC 1/3 (the spec's "
                 "preamble states the signal timestamp is always a market-structure clock time, and gives no "
                 "different definition for SPEC 7).")
    lines.append("5. **SPEC 7's 5 price bins** are the natural equal-width quintile split of [0,1]: "
                 "[0,.2) [.2,.4) [.4,.6) [.6,.8) [.8,1.0] -- the spec names 'the original 5 price bins' without "
                 "giving boundaries; this is the only unstated numeric choice in the whole spec and is recorded "
                 "here explicitly.")
    lines.append("6. **SPEC 7's TRAIN self-kill gate is reproduced deliberately.** The hypothesis text says the "
                 "original SPEC 7 'TRAIN self-kill[ed], only 2 of 5 price bins reached the 20-sample floor.' This "
                 "run checks the identical eligibility rule (>=3 of 5 bins with >=20 in EACH (bin,salience) cell) "
                 "on TRAIN before opening TEST -- consistent with non-negotiable 1 (never read test data if the "
                 "fit-stage bar already fails) and mirroring spec_M1's own self-kill pattern in this program.")
    lines.append("7. **Clause 3 (fee-inclusive breakeven) formula**, unspecified in the pass_bar text, follows "
                 "spec_M1's precedent: breakeven_win_rate = mean(entry_price) + mean(entry_fee), both dollars/ct.")
    lines.append("")
    for leg, title in (("SPEC1", "SPEC 1 -- horizon-conditional calibration fade (H=2h, rung_class=B)"),
                        ("SPEC3", "SPEC 3 -- thin-book longshot fade (H=2h, rung_class=B)"),
                        ("SPEC7", "SPEC 7 -- salient-threshold anchoring bias (rung_class=T, not a t-test)")):
        lines.append(f"## {title}")
        d = r[leg]
        lines.append(f"**VERDICT: {d['verdict']}**")
        if d.get("verdict_reason"):
            lines.append(f"Reason: {d['verdict_reason']}")
        lines.append("")
        if leg == "SPEC1" and "isotonic_fit_n" in d:
            lines.append(f"- Isotonic FIT sample (TRAIN, pooled 8 cities): n={d['isotonic_fit_n']}")
        if leg in ("SPEC1", "SPEC3") and "n_qualifying" in d:
            lines.append(f"- TEST qualifying entries: n={d['n_qualifying']}, distinct settlement-date clusters={d.get('n_dates')}")
            if "clauses" in d:
                lines.append(f"- print-weighted mean net EV: {d['print_weighted_mean_c']:.4f} c/ct")
                lines.append(f"- contract-weighted mean net EV: {d['contract_weighted_mean_c']:.4f} c/ct")
                lines.append(f"- day-clustered t (calendar-date clusters, pooled across cities) = "
                             f"{d['day_clustered_t']}, df={d['df']}, exact bar (alpha={r['alpha_per_leg']:.7f})="
                             f"{d['t_bar_exact']:.4f}")
                lines.append(f"- win rate {d['wins']}/{d['n_for_wilson']}, Wilson 95% LB={d['wilson_lb']}, "
                             f"fee-inclusive breakeven={d['breakeven_win_rate']:.4f}")
                lines.append(f"- robustness (drop 5 best settlement-date clusters {d['dropped_5_best_dates']}): "
                             f"{d['robust_mean_after_drop5_c']}")
                lines.append(f"- per-city stats: {d['city_stats']}")
                lines.append(f"- cities with n>=25: {d['qualifying_cities_ge25']}, overall sign={d['overall_sign']}, "
                             f"sign-matching cities={d['city_sign_match_count']}")
                lines.append(f"- clauses: {d['clauses']}")
        if leg == "SPEC7":
            lines.append(f"- TRAIN: n_obs={d.get('train_n_obs')}, drops={d.get('train_drop')}, "
                         f"eligible_bins={d.get('train_eligible_bins')}")
            lines.append(f"- TRAIN bin detail: {d.get('train_bin_detail')}")
            if "test_n_obs" in d:
                lines.append(f"- TEST: n_obs={d.get('test_n_obs')}, drops={d.get('test_drop')}, "
                             f"eligible_bins={d.get('test_eligible_bins')}")
                lines.append(f"- TEST bin detail: {d.get('test_bin_detail')}")
                lines.append(f"- bins with |gap|>=0.04: {d.get('big_gap_bins (|gap|>=0.04)')}, "
                             f"sign_agreement={d.get('sign_agreement')}")
        lines.append("")
    lines.append(f"## D1 OVERALL VERDICT: {r['verdict']}")
    lines.append("(D1 as a whole is a PASS only if a leg passes; legs do not pool, per the frozen pass_bar text.)")
    lines.append("")
    lines.append("## Skip ledger (mandatory -- every dropped rung/bin, with reason)")
    for leg in ("SPEC1", "SPEC3", "SPEC7"):
        ledger = r["skip_ledger"].get(leg, [])
        lines.append(f"### {leg}: {len(ledger)} skip entries")
        reason_counts = {}
        for s in ledger:
            reason_counts[s["reason"]] = reason_counts.get(s["reason"], 0) + 1
        lines.append(f"By reason: {reason_counts}")
        lines.append("")
        lines.append("<details><summary>full skip ledger</summary>")
        lines.append("")
        lines.append("```")
        for s in ledger:
            lines.append(json.dumps(s, default=str))
        lines.append("```")
        lines.append("</details>")
        lines.append("")
    lines.append("## Run log")
    lines.append("```")
    lines.extend(log_lines)
    lines.append("```")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("```")
    lines.append("python venue_expansion/cache/D1/d1_markets_pull.py   # -> cache/D1/markets_universe.json")
    lines.append("python venue_expansion/cache/D1/d1_tape_pull.py      # -> cache/D1/tape/shard-*.parquet (all 16)")
    lines.append("python venue_expansion/spec_D1.py                    # -> out/spec_D1.json, out/spec_D1.md")
    lines.append("```")
    open(OUT_MD, "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
