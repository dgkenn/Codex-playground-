#!/usr/bin/env python3
"""kwx_fill_quality.py -- FILL-QUALITY RECONCILIATION harness for the K-WX $10 live canary.

The go-live runbook's whole point is proving live == tested. kwx_forward.py already owns the tight
PnL/win-rate gate (settle vs backtest expectation). THIS unit owns the narrower, earlier question:
when a live order actually goes out, did it fill the way our models said it would? Three sub-questions:

  1. FILL RATIO + PRICE: joins kwx_exec_log.jsonl LIVE fills (kalshi_exec.py, status="live"/"live_error")
     to the kwx_runner_plan.jsonl plan record for the same ticker/moment (requested count, cap_c = the
     ask observed at detection) and, where a wx_book_snapshots.jsonl book snapshot exists near the fire
     ts, to what the depth model WOULD have predicted (predicted_fill = min(requested, depth <= cap)).
     Reports fill-ratio distribution, slippage (price paid vs ask-at-detection), and the depth model's
     prediction error. Any row whose fill_state can't be determined ("unknown" -- e.g. an ambiguous retry
     send, or a live_error record) is flagged LOUDLY: it needs a human to reconcile client_order_id
     against the Kalshi UI/API before it's trusted either way.

  2. COMPETITION SIGNAL: pulls Kalshi's PUBLIC trade tape (GET /trade-api/v2/markets/trades?ticker=...)
     around the fire window for each FIRED ticker (and only fired tickers -- request volume stays tiny)
     to see whether other participants traded through the same mechanical-lock gap. The public tape is
     anonymized, so our own fill can't be excluded with certainty; counts are reported as a heuristic
     lower bound on "other" participation, clearly labeled as such.

  3. VERDICT: when n>=10 live fires have accrued, prints an honest verdict -- LIVE==TESTED (fill ratio +
     EV within stated tolerances of the paper/depth model), DEGRADED (numbers + suspected cause), or
     INSUFFICIENT DATA (today's actual state: the canary hasn't fired 10 times yet -- prints whatever has
     accrued, which is the correct and expected output right now).

PROPOSE-ONLY: reads local logs + Kalshi's PUBLIC endpoints only (no auth). Never places or touches an
order; never reads credentials.

Usage:
    python kwx_fill_quality.py --report            # real run: joins logs, pulls public trades, prints verdict
    python kwx_fill_quality.py --report --no-trades  # skip the public trades pull (faster / offline-ish)
    python kwx_fill_quality.py --selftest           # canned fixtures: full/partial/zero/unknown/trade-through
"""
import json, math, os, sys, urllib.request, urllib.error, ssl, urllib.parse, datetime as dt
import statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"

# Overridable (module-level, not constants baked into functions) so --selftest can point these at temp
# fixtures without touching the real logs -- same seam kwx_selftest.py uses for kwx_runner.STATE_PATH/PLAN_LOG.
EXEC_LOG = os.path.join(HERE, "kwx_exec_log.jsonl")     # kalshi_exec.py's append-only order log (gitignored)
PLAN_LOG = os.path.join(HERE, "kwx_runner_plan.jsonl")  # kwx_runner.py's per-fire plan log
SNAP_LOG = os.path.join(HERE, "wx_book_snapshots.jsonl")  # wx_capacity_probe.py depth snapshots (committed)

PLAN_JOIN_WINDOW_S = 10 * 60   # exec<->plan: same fire, so this should be seconds apart; 10min is generous
SNAP_JOIN_WINDOW_S = 45 * 60   # snapshots run ~every 30min through the afternoon -> allow some slop
TRADES_WINDOW_S = 5 * 60       # public trade-tape pull: +/- 5min around the fire ts

# Same backtest win-prob bar kwx_forward.py checks realized PnL against (EXP_WIN there). Used ONLY as an
# EV *proxy* here (paper cap_c price vs actual price_paid, same assumed win prob for both) -- this unit has
# no settlement join (that's kwx_forward.py's job); it isolates the FILL side of "live == tested".
EXP_WIN = 0.9965

# ---- verdict tolerances (n>=10 gate) -- deliberately loose: this is "is the fill machinery honest",
# not a tight statistical PnL test (kwx_forward.py's settle+report owns that one, with day-clustered t). ----
FILL_RATIO_TOL = 0.15   # mean live fill-ratio vs mean depth-model predicted fill-ratio (matched rows)
SLIPPAGE_TOL_C = 2.0    # mean (price paid - ask at detection), cents
EV_TOL_C = 2.0          # mean EV/ct gap (actual price vs paper/cap price), cents, via the EXP_WIN proxy


def _kalshi_fee_c(price_c):
    """Kalshi taker fee in CENTS at price_c -- same quadratic formula as kwx_runner._kalshi_fee_c /
    kwx_forward._kalshi_fee, kept independent (no import) so this unit has no hard dependency on the
    runner module and can't be broken by an unrelated runner refactor."""
    p = price_c / 100.0
    return math.ceil(0.07 * p * (1 - p) * 100)


def _ev_c(price_c, p=EXP_WIN):
    """Expected net cents/contract at price_c under the backtest win-prob bar -- a PROXY (assumes the
    backtest's win rate applies equally at the cap price and the actual paid price; no settlement lookup
    here). Used only to compare paper-model EV (at cap_c) vs actual EV (at price_paid_c), not as a
    standalone PnL claim."""
    fee_c = _kalshi_fee_c(price_c)
    return p * (100 - price_c) - (1 - p) * price_c - fee_c


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))


def _load_jsonl(path):
    """Tolerant JSONL loader: skips blank lines and torn/partial trailing lines (both exec + plan logs
    are append-only files a live process may be mid-write on)."""
    out = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _iso_to_ms(s):
    try:
        return int(dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


# ---------------- primitives ----------------
def _fill_state(rec):
    """Derive fill_state when the exec-log record doesn't already carry one (kalshi_exec.py only sets
    fill_state explicitly on the retry path -- see kalshi_exec._retry_once). A record with no interpretable
    `filled` int (live_error, or an ambiguous-send retry) is ALWAYS "unknown" -- never guessed at."""
    explicit = rec.get("fill_state")
    if explicit:
        return explicit
    filled = rec.get("filled")
    if not isinstance(filled, int) or isinstance(filled, bool):
        return "unknown"
    if filled == 0:
        return "flat"
    requested = rec.get("requested")
    if isinstance(requested, int) and not isinstance(requested, bool):
        if filled == requested:
            return "filled"
        if 0 < filled < requested:
            return "partial"
    return "unknown"


def _avg_price_paid_c(rec):
    """Best-effort extraction of the actual average price paid (cents) for a live fill, from the raw
    Kalshi create-order response. This repo has not yet inspected a real filled-live-order response body
    (the canary has placed 0 orders as of this writing), so the exact field name isn't pinned -- this is
    deliberately schema-tolerant, trying several plausible field names before falling back to the order's
    price CAP (what we were willing to pay, not proof of what we paid). Returns (price_c_or_None, source_str)
    so callers/reports can always see whether a number is MEASURED or a CAP PROXY."""
    resp = rec.get("response")
    o = resp.get("order") if isinstance(resp, dict) else None
    if not isinstance(o, dict):
        o = {}
    for key in ("average_fill_price", "avg_fill_price_cents", "average_fill_price_cents"):
        v = o.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v), f"response.order.{key}"
    for key in ("average_fill_price_dollars", "avg_fill_price_dollars"):
        v = o.get(key)
        if v is not None:
            try:
                return round(float(v) * 100, 2), f"response.order.{key} (dollars->c)"
            except Exception:
                pass
    cost, cnt = o.get("taker_fill_cost"), o.get("taker_fill_count")
    if cnt is None:
        cnt = rec.get("filled")
    if (isinstance(cost, (int, float)) and not isinstance(cost, bool)
            and isinstance(cnt, (int, float)) and not isinstance(cnt, bool) and cnt):
        return round(cost / cnt, 2), "response.order.taker_fill_cost/taker_fill_count"
    order = rec.get("order") or {}
    for key in ("yes_price", "no_price"):
        v = order.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v), f"order.{key} (cap proxy, NOT a measured fill price)"
    return None, "unavailable"


def _depth_at_cap_from_snapshot(snap, side, cap_c):
    """Contracts fillable at <= cap_c (cents) per the book snapshot, for buying `side`. Mirrors the exact
    book convention kalshi_exec._sim_depth_fill and the wx_book_snapshot_schema.md doc use: the snapshot
    stores yes_bid_levels / yes_ask_levels (yes_ask_levels IS the buy-YES ask ladder, already derived from
    resting NO bids). Buying NO instead lifts the resting YES bids: a YES bid at p is a NO ask at (100-p),
    so the buy-NO ask ladder is derived here from yes_bid_levels the same way _sim_depth_fill derives it
    from the live orderbook's opposite side."""
    if side == "yes":
        levels = snap.get("yes_ask_levels") or []
        return sum(sz for p, sz in levels if isinstance(p, (int, float)) and p <= cap_c)
    levels = snap.get("yes_bid_levels") or []
    total = 0
    for p, sz in levels:
        if not isinstance(p, (int, float)):
            continue
        ask = 100 - p
        if 1 <= ask <= 99 and ask <= cap_c:
            total += sz
    return total


def _index_by_ticker(rows):
    idx = defaultdict(list)
    for r in rows:
        t = r.get("ticker")
        if t:
            idx[t].append(r)
    return idx


def _nearest_by_ts(candidates, ts_ms, window_ms, ts_of):
    """candidates: list of arbitrary rows; ts_of(row) -> ms or None. Returns the row nearest ts_ms within
    window_ms, or None."""
    best, best_d = None, None
    if ts_ms is None:
        return None
    for r in candidates:
        rt = ts_of(r)
        if rt is None:
            continue
        d = abs(rt - ts_ms)
        if d <= window_ms and (best_d is None or d < best_d):
            best, best_d = r, d
    return best


# ---------------- public trades pull (competition signal) ----------------
def _fetch_trades(ticker, center_ts_ms, window_s=TRADES_WINDOW_S, limit=200):
    """PUBLIC trade tape for `ticker` in a +/- window_s window around center_ts_ms. Returns None on ANY
    fetch error (distinct from [] = confirmed no trades in the window) so callers don't mistake a network
    blip for silence. Bounded request: one call per fired ticker, tight time window, single page (limit)."""
    min_ts = int(center_ts_ms / 1000) - window_s
    max_ts = int(center_ts_ms / 1000) + window_s
    url = (f"{KBASE}/markets/trades?ticker={urllib.parse.quote(ticker)}"
           f"&min_ts={min_ts}&max_ts={max_ts}&limit={limit}")
    try:
        d = _get(url, timeout=8)
        return d.get("trades") if isinstance(d, dict) else None
    except Exception:
        return None


def _competition_signal(ticker, ts_ms, side, cap_c):
    """Did anyone ELSE trade through the same mechanical-lock gap we fired into? The public tape has no
    account identifier, so our own fill can't be excluded with certainty -- `other_likely_count` is a
    heuristic lower bound (raw same-side/in-gap trade count minus 1, presumed ours), reported alongside the
    raw count so nothing is silently laundered into a false-precise number."""
    trades = _fetch_trades(ticker, ts_ms)
    if trades is None:
        return {"status": "unavailable"}
    price_key = "yes_price_dollars" if side == "yes" else "no_price_dollars"
    through = []
    for t in trades:
        try:
            pc = round(float(t.get(price_key)) * 100, 2)
        except (TypeError, ValueError):
            continue
        if t.get("taker_side") == side and cap_c is not None and pc <= cap_c + 0.01:
            through.append({"trade_id": t.get("trade_id"), "price_c": pc,
                            "created_time": t.get("created_time")})
    return {"status": "ok", "n_trades_window": len(trades), "n_trades_through_our_gap": len(through),
            "other_likely_count": max(0, len(through) - 1), "sample": through[:5]}


# ---------------- the join ----------------
def build_rows(exec_log=None, plan_log=None, snap_log=None, fetch_trades=True):
    exec_log = exec_log if exec_log is not None else EXEC_LOG
    plan_log = plan_log if plan_log is not None else PLAN_LOG
    snap_log = snap_log if snap_log is not None else SNAP_LOG

    exec_rows_all = _load_jsonl(exec_log)
    exec_rows = [r for r in exec_rows_all if r.get("live") is True]
    n_blocked = sum(1 for r in exec_rows if str(r.get("status", "")).startswith("BLOCKED"))
    plans = _load_jsonl(plan_log)
    snaps = _load_jsonl(snap_log)

    plan_idx = _index_by_ticker(plans)
    snap_idx = _index_by_ticker(snaps)

    rows = []
    for rec in exec_rows:
        status = rec.get("status")
        if status not in ("live", "live_error"):
            continue   # BLOCKED_* -> no order was ever sent; nothing to reconcile as a fill
        ticker = rec.get("ticker")   # NOTE: live_error records carry no ticker (kalshi_exec.py gap) -> None
        ts_ms = rec.get("ts")

        plan = _nearest_by_ts(plan_idx.get(ticker, []), ts_ms, PLAN_JOIN_WINDOW_S * 1000,
                              lambda p: p.get("ts")) if ticker else None
        side = rec.get("side") or (plan.get("side") if plan else None) or "yes"
        requested = rec.get("requested")
        filled = rec.get("filled")
        fstate = _fill_state(rec)
        cap_c = plan.get("cap_c") if plan else None   # "the ask at detection" the runner fired against

        price_paid_c, price_source = _avg_price_paid_c(rec)
        slippage_c = (price_paid_c - cap_c) if (price_paid_c is not None and cap_c is not None) else None

        snap = _nearest_by_ts(snap_idx.get(ticker, []), ts_ms, SNAP_JOIN_WINDOW_S * 1000,
                              lambda s: _iso_to_ms(s.get("ts_utc"))) if ticker else None
        predicted_fill = None
        if snap is not None and cap_c is not None and isinstance(requested, int):
            predicted_fill = min(requested, _depth_at_cap_from_snapshot(snap, side, cap_c))
        pred_error = (filled - predicted_fill) if (isinstance(filled, int) and not isinstance(filled, bool)
                                                    and predicted_fill is not None) else None

        ev_paper_c = _ev_c(cap_c) if cap_c is not None else None
        ev_actual_c = _ev_c(price_paid_c) if price_paid_c is not None else None
        ev_gap_c = (ev_actual_c - ev_paper_c) if (ev_actual_c is not None and ev_paper_c is not None) else None

        fill_ratio = None
        if (isinstance(filled, int) and not isinstance(filled, bool)
                and isinstance(requested, int) and requested > 0):
            fill_ratio = filled / requested

        row = {
            "ticker": ticker, "ts": ts_ms, "side": side, "status": status,
            "requested": requested, "filled": filled, "fill_state": fstate, "fill_ratio": fill_ratio,
            "cap_c_ask_at_detection": cap_c, "plan_matched": plan is not None,
            "price_paid_c": price_paid_c, "price_source": price_source, "slippage_c": slippage_c,
            "snapshot_matched": snap is not None,
            "predicted_fill": predicted_fill, "pred_error": pred_error,
            "ev_paper_c": ev_paper_c, "ev_actual_c": ev_actual_c, "ev_gap_c": ev_gap_c,
        }
        if fetch_trades and ticker and ts_ms:
            row["trades"] = _competition_signal(ticker, ts_ms, side, cap_c)
        rows.append(row)
    return rows, n_blocked


# ---------------- verdict ----------------
def compute_verdict(rows):
    """Returns (verdict_str, detail_dict). n>=10 is the decisiveness gate; below it we always say
    INSUFFICIENT DATA and just report what's accrued -- that's the correct, EXPECTED output for a canary
    that has fired fewer than 10 times, not a failure of this harness."""
    n = len(rows)
    detail = {"n": n}
    if n == 0:
        detail["reason"] = "0 live fires logged yet"
        return "INSUFFICIENT DATA", detail

    unknown = [r for r in rows if r["fill_state"] == "unknown"]
    known = [r for r in rows if r["fill_state"] != "unknown"]
    detail["n_unknown"] = len(unknown)

    fill_ratios = [r["fill_ratio"] for r in known if r["fill_ratio"] is not None]
    pred_ratios = [r["predicted_fill"] / r["requested"] for r in known
                   if r.get("predicted_fill") is not None and r.get("requested")]
    slippages = [r["slippage_c"] for r in rows if r["slippage_c"] is not None]
    ev_gaps = [r["ev_gap_c"] for r in rows if r["ev_gap_c"] is not None]

    detail["mean_fill_ratio"] = st.mean(fill_ratios) if fill_ratios else None
    detail["mean_predicted_fill_ratio"] = st.mean(pred_ratios) if pred_ratios else None
    detail["mean_slippage_c"] = st.mean(slippages) if slippages else None
    detail["mean_ev_gap_c"] = st.mean(ev_gaps) if ev_gaps else None

    if n < 10:
        return "INSUFFICIENT DATA", detail

    causes = []
    fr_ok = True
    if detail["mean_fill_ratio"] is not None and detail["mean_predicted_fill_ratio"] is not None:
        gap = detail["mean_fill_ratio"] - detail["mean_predicted_fill_ratio"]
        detail["fill_ratio_gap_vs_model"] = gap
        if abs(gap) > FILL_RATIO_TOL:
            fr_ok = False
            cause = ("live filling WORSE than the depth model predicted -- adverse selection / stale book"
                      if gap < 0 else "live filling BETTER than the depth model predicted -- model too conservative")
            causes.append(f"fill ratio {gap:+.1%} vs depth model ({cause})")
    elif detail["mean_fill_ratio"] is not None and detail["mean_fill_ratio"] < (1 - FILL_RATIO_TOL):
        fr_ok = False
        causes.append(f"mean fill ratio {detail['mean_fill_ratio']:.1%} is low, but no matched book "
                      "snapshots exist to attribute a cause (widen SNAP_JOIN_WINDOW_S or check the "
                      "depthprobe workflow is running)")

    slip_ok = True
    if detail["mean_slippage_c"] is not None and abs(detail["mean_slippage_c"]) > SLIPPAGE_TOL_C:
        slip_ok = False
        causes.append(f"mean slippage {detail['mean_slippage_c']:+.2f}c vs ask-at-detection "
                      "(paying through the quoted ask -- detection/order latency or a thin book)")

    ev_ok = True
    if detail["mean_ev_gap_c"] is not None and abs(detail["mean_ev_gap_c"]) > EV_TOL_C:
        ev_ok = False
        causes.append(f"mean EV/ct gap {detail['mean_ev_gap_c']:+.2f}c vs the paper model's assumed price")

    detail["causes"] = causes
    if fr_ok and slip_ok and ev_ok:
        verdict = ("LIVE == TESTED" if not unknown else
                   "LIVE == TESTED (numbers) -- BUT UNKNOWN-STATE ROWS NEED MANUAL RECONCILIATION")
    else:
        verdict = "DEGRADED"
    return verdict, detail


# ---------------- report ----------------
def print_report(rows, n_blocked=0):
    n = len(rows)
    print("=== K-WX FILL-QUALITY RECONCILIATION (live canary) ===")
    print(f"  live order attempts (status=live/live_error): {n}")
    if n_blocked:
        print(f"  (+{n_blocked} guard-BLOCKED order(s) while live -- no order sent, excluded from fill stats)")
    if n == 0:
        verdict, detail = compute_verdict(rows)
        print("  no live fills logged yet in kwx_exec_log.jsonl.")
        print(f"  VERDICT: {verdict} -- {detail.get('reason', '')}")
        return verdict, detail

    unknown = [r for r in rows if r["fill_state"] == "unknown"]
    known = [r for r in rows if r["fill_state"] != "unknown"]
    fill_ratios = sorted(r["fill_ratio"] for r in known if r["fill_ratio"] is not None)
    slippages = [r["slippage_c"] for r in rows if r["slippage_c"] is not None]
    pred_errors = [r["pred_error"] for r in rows if r["pred_error"] is not None]
    n_snap_matched = sum(1 for r in rows if r["snapshot_matched"])

    print(f"\n  -- fill ratio (filled/requested), n={len(fill_ratios)} known --")
    if fill_ratios:
        print(f"     mean {st.mean(fill_ratios):.1%}  median {st.median(fill_ratios):.1%}  "
              f"min {min(fill_ratios):.1%}  max {max(fill_ratios):.1%}")
    else:
        print("     (no rows with a determinable fill ratio)")

    print(f"\n  -- slippage: price paid - ask at detection (cents), n={len(slippages)} --")
    if slippages:
        print(f"     mean {st.mean(slippages):+.2f}c" +
              (f"  stdev {st.stdev(slippages):.2f}c" if len(slippages) > 1 else ""))
    else:
        print("     (no rows with both a measured price and a matched plan record)")

    print(f"\n  -- depth-model prediction error: filled - predicted_fill, n={len(pred_errors)} "
          f"({n_snap_matched}/{n} rows matched a book snapshot) --")
    if pred_errors:
        mae = st.mean(abs(e) for e in pred_errors)
        print(f"     mean {st.mean(pred_errors):+.2f}  MAE {mae:.2f}")
    else:
        print("     (no rows matched a book snapshot within the join window)")

    if unknown:
        print(f"\n  !!! {len(unknown)} ROW(S) fill_state=UNKNOWN -- NEEDS MANUAL RECONCILIATION !!!")
        for r in unknown:
            print(f"      ticker={r['ticker']!r} ts={r['ts']} status={r['status']} "
                  f"requested={r['requested']} filled={r['filled']} price_source={r['price_source']} "
                  "-- reconcile against Kalshi order history by client_order_id before assuming flat/filled")

    trades_rows = [r for r in rows if "trades" in r]
    if trades_rows:
        print(f"\n  -- competition signal (public trade tape, {len(trades_rows)} ticker(s) checked) --")
        for r in trades_rows:
            t = r["trades"]
            if t.get("status") != "ok":
                print(f"     {r['ticker']}: trade-tape fetch unavailable")
                continue
            flag = " <- someone else may be harvesting this gap too" if t["other_likely_count"] > 0 else ""
            print(f"     {r['ticker']}: {t['n_trades_window']} trade(s) in window, "
                  f"{t['n_trades_through_our_gap']} through our gap "
                  f"(other_likely~={t['other_likely_count']}, heuristic -- can't exclude our own fill "
                  f"on the anonymized public tape){flag}")

    verdict, detail = compute_verdict(rows)
    print(f"\n  VERDICT: {verdict}")
    print(f"    n={detail['n']}  n_unknown={detail.get('n_unknown', 0)}")
    if detail.get("mean_fill_ratio") is not None:
        print(f"    mean fill ratio: {detail['mean_fill_ratio']:.1%}"
              + (f"  (predicted: {detail['mean_predicted_fill_ratio']:.1%})"
                 if detail.get("mean_predicted_fill_ratio") is not None else "  (no matched predictions)"))
    if detail.get("mean_slippage_c") is not None:
        print(f"    mean slippage: {detail['mean_slippage_c']:+.2f}c")
    if detail.get("mean_ev_gap_c") is not None:
        print(f"    mean EV/ct gap vs paper model: {detail['mean_ev_gap_c']:+.2f}c")
    if detail.get("causes"):
        print("    suspected cause(s):")
        for c in detail["causes"]:
            print(f"      - {c}")
    if verdict == "INSUFFICIENT DATA":
        print(f"    (n<10: expected today for a fresh $10 canary -- keep the runner accruing live fires.)")
    return verdict, detail


# ==================================================================================================
#                                          --selftest
# ==================================================================================================
FAILURES = []


def _check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def selftest():
    print("kwx_fill_quality.py --selftest\n")

    # 0) primitives -----------------------------------------------------------------------------
    print("0) primitives:")
    _check("_kalshi_fee_c(50c) == 2c (ceil(0.07*.5*.5*100)=1.75->2)", _kalshi_fee_c(50) == 2)
    _check("_ev_c favors cheaper price (30c > 90c)", _ev_c(30) > _ev_c(90))

    _check("_fill_state: full fill", _fill_state({"filled": 10, "requested": 10}) == "filled")
    _check("_fill_state: partial fill", _fill_state({"filled": 4, "requested": 10}) == "partial")
    _check("_fill_state: zero fill", _fill_state({"filled": 0, "requested": 10}) == "flat")
    _check("_fill_state: filled=None -> unknown", _fill_state({"filled": None, "requested": 10}) == "unknown")
    _check("_fill_state: explicit fill_state respected",
           _fill_state({"filled": None, "fill_state": "unknown"}) == "unknown")
    _check("_fill_state: live_error record (no filled key) -> unknown", _fill_state({"status": "live_error"}) == "unknown")

    rec_full = {"response": {"order": {"average_fill_price": 82}}}
    p, src = _avg_price_paid_c(rec_full)
    _check("_avg_price_paid_c: average_fill_price field", p == 82.0 and "average_fill_price" in src)

    rec_dollars = {"response": {"order": {"average_fill_price_dollars": "0.8500"}}}
    p, src = _avg_price_paid_c(rec_dollars)
    _check("_avg_price_paid_c: dollars field converts to cents", p == 85.0, (p, src))

    rec_cost = {"response": {"order": {"taker_fill_cost": 400, "taker_fill_count": 5}}}
    p, src = _avg_price_paid_c(rec_cost)
    _check("_avg_price_paid_c: cost/count derives vwap (400/5=80)", p == 80.0, (p, src))

    rec_fallback = {"order": {"yes_price": 91}}
    p, src = _avg_price_paid_c(rec_fallback)
    _check("_avg_price_paid_c: falls back to order cap, labeled as such", p == 91.0 and "cap proxy" in src)

    _check("_avg_price_paid_c: nothing available -> (None, 'unavailable')", _avg_price_paid_c({}) == (None, "unavailable"))

    snap = {"yes_ask_levels": [[80, 5], [85, 10]], "yes_bid_levels": [[70, 4], [60, 20]]}
    _check("_depth_at_cap_from_snapshot: yes side sums levels <= cap",
           _depth_at_cap_from_snapshot(snap, "yes", 85) == 15)
    _check("_depth_at_cap_from_snapshot: yes side excludes levels > cap",
           _depth_at_cap_from_snapshot(snap, "yes", 82) == 5)
    # NO ask ladder derived from yes_bid_levels: bid 70 -> no-ask 30; bid 60 -> no-ask 40
    _check("_depth_at_cap_from_snapshot: no side derives from yes bids (ask=100-bid)",
           _depth_at_cap_from_snapshot(snap, "no", 35) == 4)
    _check("_depth_at_cap_from_snapshot: no side, wider cap includes both derived levels",
           _depth_at_cap_from_snapshot(snap, "no", 40) == 24)

    # 1) build_rows join: full / partial / zero / unknown, offline (no network) --------------------
    print("\n1) build_rows join over canned exec/plan/snapshot fixtures:")
    import tempfile
    tmp = tempfile.mkdtemp()
    exec_log = os.path.join(tmp, "exec.jsonl")
    plan_log = os.path.join(tmp, "plan.jsonl")
    snap_log = os.path.join(tmp, "snap.jsonl")

    T0 = 1_800_000_000_000  # arbitrary fixed ms epoch, shared across fixture rows
    exec_rows = [
        # FULL FILL: requested==filled, price via average_fill_price
        {"status": "live", "ticker": "KXHIGHDEN-26JUL19-B90.5", "requested": 10, "filled": 10,
         "order_status": "executed", "response": {"order": {"average_fill_price": 81}},
         "ts": T0, "live": True},
        # PARTIAL FILL: book thinner than requested
        {"status": "live", "ticker": "KXHIGHMIA-26JUL19-B90.5", "requested": 8, "filled": 3,
         "order_status": "executed", "response": {"order": {"taker_fill_cost": 279, "taker_fill_count": 3}},
         "ts": T0 + 1000, "live": True},
        # ZERO FILL: confirmed flat (ask moved before we hit it)
        {"status": "live", "ticker": "KXLOWTDEN-26JUL19-B64.5", "requested": 5, "filled": 0,
         "order_status": "canceled", "response": {"order": {}}, "ts": T0 + 2000, "live": True},
        # UNKNOWN: ambiguous retry send (kalshi_exec._retry_once's fill_state="unknown" path)
        {"status": "live", "ticker": "KXHIGHCHI-26JUL19-B88.5", "requested": 6, "filled": None,
         "fill_state": "unknown", "ts": T0 + 3000, "live": True},
        # UNKNOWN (via missing ticker): live_error record -- kalshi_exec.py's error path carries no ticker
        {"status": "live_error", "code": 400, "body": "bad request", "ts": T0 + 4000, "live": True},
        # DRY-RUN row (live=False) -- must be excluded entirely from the live join
        {"status": "DRY_RUN", "ticker": "KXHIGHDEN-26JUL19-B90.5", "requested": 10, "filled": 10,
         "ts": T0 + 5000, "live": False},
        # BLOCKED while live -- order never sent, must be excluded from fill stats but counted separately
        {"status": "BLOCKED_HALT", "ticker": "KXHIGHAUS-26JUL19-B95.5", "reason": "kill-switch",
         "ts": T0 + 6000, "live": True},
    ]
    plan_rows = [
        {"ticker": "KXHIGHDEN-26JUL19-B90.5", "side": "yes", "cap_c": 80, "requested": 10, "ts": T0 - 500},
        {"ticker": "KXHIGHMIA-26JUL19-B90.5", "side": "yes", "cap_c": 93, "requested": 8, "ts": T0 + 500},
        {"ticker": "KXLOWTDEN-26JUL19-B64.5", "side": "no", "cap_c": 96, "requested": 5, "ts": T0 + 1500},
    ]
    snap_ts = dt.datetime.fromtimestamp(T0 / 1000, tz=dt.timezone.utc).isoformat()
    snap_rows = [
        # matches the FULL FILL ticker: depth well above requested -> predicted_fill == requested (10)
        {"ticker": "KXHIGHDEN-26JUL19-B90.5", "ts_utc": snap_ts,
         "yes_ask_levels": [[78, 3], [80, 20]], "yes_bid_levels": []},
        # matches the PARTIAL FILL ticker: depth at cap (93c) is only 3 -> predicted_fill == 3 (matches live)
        {"ticker": "KXHIGHMIA-26JUL19-B90.5", "ts_utc": snap_ts,
         "yes_ask_levels": [[93, 3]], "yes_bid_levels": []},
    ]
    with open(exec_log, "w") as f:
        for r in exec_rows:
            f.write(json.dumps(r) + "\n")
    with open(plan_log, "w") as f:
        for r in plan_rows:
            f.write(json.dumps(r) + "\n")
    with open(snap_log, "w") as f:
        for r in snap_rows:
            f.write(json.dumps(r) + "\n")
    # a torn trailing line -- must not crash the loader
    with open(exec_log, "a") as f:
        f.write('{"status": "live", "ticker": "TORN"')

    rows, n_blocked = build_rows(exec_log=exec_log, plan_log=plan_log, snap_log=snap_log, fetch_trades=False)
    _check("build_rows: torn trailing line skipped, not crashed", True)
    _check("build_rows: excludes DRY_RUN (live=False) rows", all(r["ticker"] != "KXHIGHDEN-26JUL19-B90.5"
           or r["filled"] == 10 for r in rows) and len([r for r in rows if r["status"] == "DRY_RUN"]) == 0)
    _check("build_rows: excludes BLOCKED_* rows from the join", not any("BLOCKED" in str(r["status"]) for r in rows))
    _check("build_rows: BLOCKED row counted separately", n_blocked == 1, n_blocked)
    _check("build_rows: 5 live/live_error rows joined", len(rows) == 5, len(rows))

    by_ticker = {r["ticker"]: r for r in rows if r["ticker"]}
    full = by_ticker["KXHIGHDEN-26JUL19-B90.5"]
    _check("full fill: fill_state=filled", full["fill_state"] == "filled")
    _check("full fill: fill_ratio == 1.0", full["fill_ratio"] == 1.0)
    _check("full fill: price paid extracted (81c)", full["price_paid_c"] == 81.0)
    _check("full fill: slippage vs cap_c=80 -> +1c", full["slippage_c"] == 1.0, full["slippage_c"])
    _check("full fill: snapshot matched, predicted_fill==requested (10)", full["predicted_fill"] == 10, full)
    _check("full fill: pred_error == 0 (model was right)", full["pred_error"] == 0, full)

    part = by_ticker["KXHIGHMIA-26JUL19-B90.5"]
    _check("partial fill: fill_state=partial", part["fill_state"] == "partial")
    _check("partial fill: fill_ratio == 3/8", abs(part["fill_ratio"] - 3 / 8) < 1e-9)
    _check("partial fill: vwap derived from cost/count (93c)", part["price_paid_c"] == 93.0)
    _check("partial fill: depth model predicted the SAME partial (3) -> pred_error 0",
           part["predicted_fill"] == 3 and part["pred_error"] == 0, part)

    zero = by_ticker["KXLOWTDEN-26JUL19-B64.5"]
    _check("zero fill: fill_state=flat", zero["fill_state"] == "flat")
    _check("zero fill: fill_ratio == 0.0", zero["fill_ratio"] == 0.0)

    unk = by_ticker["KXHIGHCHI-26JUL19-B88.5"]
    _check("unknown (ambiguous retry): fill_state=unknown", unk["fill_state"] == "unknown")

    unk_rows = [r for r in rows if r["fill_state"] == "unknown"]
    _check("2 unknown rows total (ambiguous retry + ticker-less live_error)", len(unk_rows) == 2, len(unk_rows))
    _check("live_error row present with ticker=None", any(r["status"] == "live_error" and r["ticker"] is None
           for r in rows))

    # 2) trade-through / competition signal (monkeypatched _fetch_trades -- no network) -------------
    print("\n2) competition signal / trade-through detection:")
    global _fetch_trades   # _competition_signal looks this up as a module global at call time
    _orig_fetch = _fetch_trades

    def _fake_trades_through(ticker, ts_ms, window_s=TRADES_WINDOW_S, limit=200):
        # our own fill @80c + one other participant @79c, both same-side "yes", both <= cap 80c
        return [
            {"trade_id": "ours", "taker_side": "yes", "yes_price_dollars": "0.80", "created_time": "t0"},
            {"trade_id": "other", "taker_side": "yes", "yes_price_dollars": "0.79", "created_time": "t1"},
            {"trade_id": "unrelated_no", "taker_side": "no", "yes_price_dollars": "0.20", "created_time": "t2"},
        ]

    _fetch_trades = _fake_trades_through
    try:
        sig = _competition_signal("KXHIGHDEN-26JUL19-B90.5", T0, "yes", 80)
    finally:
        _fetch_trades = _orig_fetch
    _check("trade-through: status ok", sig["status"] == "ok", sig)
    _check("trade-through: 3 trades in window", sig["n_trades_window"] == 3, sig)
    _check("trade-through: 2 trades through our gap (yes side, <=80c)", sig["n_trades_through_our_gap"] == 2, sig)
    _check("trade-through: other_likely_count == 1 (2 minus presumed-ours)", sig["other_likely_count"] == 1, sig)

    _fetch_trades = lambda *a, **k: None
    try:
        sig_unavail = _competition_signal("X", T0, "yes", 80)
    finally:
        _fetch_trades = _orig_fetch
    _check("trade fetch failure -> status unavailable (not silently 0)", sig_unavail["status"] == "unavailable")

    # 3) verdict logic on synthetic row sets (bypasses files entirely) ------------------------------
    print("\n3) compute_verdict:")

    def _row(fill_state="filled", fill_ratio=1.0, predicted_fill=None, requested=10, slippage_c=0.0, ev_gap_c=0.0):
        return {"fill_state": fill_state, "fill_ratio": fill_ratio, "predicted_fill": predicted_fill,
                "requested": requested, "slippage_c": slippage_c, "ev_gap_c": ev_gap_c}

    few = [_row() for _ in range(5)]
    v, d = compute_verdict(few)
    _check("n<10 -> INSUFFICIENT DATA", v == "INSUFFICIENT DATA", v)

    good = [_row(fill_ratio=1.0, predicted_fill=10, slippage_c=0.5, ev_gap_c=0.2) for _ in range(10)]
    v, d = compute_verdict(good)
    _check("n=10, everything on-model -> LIVE == TESTED", v == "LIVE == TESTED", (v, d))

    bad = [_row(fill_ratio=0.3, predicted_fill=9, slippage_c=5.0, ev_gap_c=4.0) for _ in range(10)]
    v, d = compute_verdict(bad)
    _check("n=10, fill ratio/slippage/EV all off-model -> DEGRADED", v == "DEGRADED", (v, d))
    _check("DEGRADED verdict lists suspected causes", len(d.get("causes", [])) >= 2, d.get("causes"))

    unknown_but_ok = good[:9] + [_row(fill_state="unknown", fill_ratio=None, ev_gap_c=None, slippage_c=None)]
    v, d = compute_verdict(unknown_but_ok)
    _check("on-model numbers but 1 unknown row -> flags manual reconciliation, not silently clean",
           v.startswith("LIVE == TESTED") and "MANUAL RECONCILIATION" in v, v)

    print("\n" + ("ALL CHECKS PASSED" if not FAILURES else f"{len(FAILURES)} CHECK(S) FAILED: {FAILURES}"))
    return 1 if FAILURES else 0


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        sys.exit(selftest())
    fetch_trades = "--no-trades" not in argv
    rows, n_blocked = build_rows(fetch_trades=fetch_trades)
    print_report(rows, n_blocked=n_blocked)


if __name__ == "__main__":
    main()
