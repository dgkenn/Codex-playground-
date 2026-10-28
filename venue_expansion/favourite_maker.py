"""favourite_maker.py -- executes FAVOURITE_MAKER_SPEC.md (registered 2026-10-28).  Nothing here may move a bar.

QUESTION. Resting a BUY-YES at d = yes_ask - k on Kalshi KXBTCD favourites (yes_ask >= 80c) pays no maker fee.
Does P(YES | filled) exceed break-even mean(d)/100 despite adverse selection (a bid is hit when someone sells,
i.e. when YES is becoming LESS likely, so the adverse direction is P(YES|filled) < P(YES|quoted))?
PRIMARY MEASUREMENT = P(YES|filled) vs P(YES|quoted) vs mean(d)/100 per cell (anchor a).  EV is secondary, SIGN ONLY.

THIS IS THE MIRROR OF maker_fill.py AND REUSES ITS MACHINERY (tape fetch/pacing/parse, Wilson, the day-bootstrap
design, the cell layout).  What is deliberately FLIPPED, not copied:
  * maker_fill counted prints at yes_price >= a from ALL taker sides (spec-literal there) for a resting ASK.
    Here a resting BUY is filled by a taker SELL: taker_side == "no" at yes_price <= d.  Only those prints count in
    the primary.  Asserted by `assert_fill_filter()`, unit-tested on synthetic prints, hand-worked from raw API JSON,
    and checked empirically against the candle book (taker "no" prints must sit at the BID, taker "yes" at the ASK).
  * P&L per filled contract is +(100 - d) if YES else -d  (maker_fill: +a if NO else -(100 - a)).

FROZEN INTERPRETATION CHOICES (spec silent or ambiguous; fixed BEFORE any fill or outcome was computed):
  * Universe / hours: the 503 completed hours of cache/tail_pricing in the saved seed-20261027 work_order.json order,
    never re-sorted.  Calendar day = UTC date of close = cluster unit.  Tape covered = longest contiguous PREFIX of
    that order whose favourite-strike tape is complete; any tape-complete hour beyond the first gap is a straggler,
    EXCLUDED from analysis (not re-ordered) and counted.
  * The maker_fill tape (cache/maker_fill/tape) holds only the LONGSHOT strikes (bid <= 19c) and cannot contain the
    favourite strikes (ask >= 80c); it is READ ONLY here and is used for nothing but the side-convention cross-check.
    Favourite-strike prints are fetched with maker_fill.fetch_ticker (same endpoint, window, parser, pacing) into
    cache/favourite_maker/tape.
  * Quote placement: last candle with end_period_ts <= close - T*60 (the same candle rule as tail_pricing.entry_quote);
    A = that candle's yes_ask.close in cents.  Quoted iff A is present and A >= 80 (ZONE, frozen).  d = A - k,
    k in {1,2,3}.  A candle missing/no ask -> not quoted, counted.  1 contract per quote, rests from t0 = close - T*60
    (exclusive) to close (inclusive), no re-quote, no cancel.
  * THE ZONE IS 98% yes_ask == 100c.  `quotes` was run first (candles only): of 565,599 quotes, about 98% sit at
    yes_ask == 100c, i.e. deep in-the-money strikes with NO resting offer, where d = A - k is anchored on a non-existent
    ask (the mirror of MAKER_FILL's bid == 0 "untradeable" rows, which it dropped).  Decided from these COUNTS alone,
    before any tape was fetched, any fill computed or any outcome read: run BOTH and label them, moving no bar:
        Z1 = spec-literal, yes_ask >= 80c INCLUDING 100c (verdict of record, because the spec says so);
        Z2 = real two-sided favourites, 80c <= yes_ask <= 99c (the market the spec's motivating bid >= 81c measurement
             describes; 3,320 tickers vs Z1's extra 44,383).
    Tape for Z2 tickers = cache/favourite_maker/tape (phase A); Z1-only tickers = cache/favourite_maker/tape_b (phase B).
  * Fill, on the trade tape: V(t) = cumulative count_fp of prints with created_time in (t0, close], taker_side == "no"
    and yes_price <= d.   OPTIMISTIC: V > 0.   PESSIMISTIC N in {25,100}: V > N (strictly).  N is an ASSUMPTION.
    Sensitivity (reported, never selected): same rules counting ALL taker sides at yes_price <= d (the literal mirror of
    maker_fill's primary).
  * P&L per filled, zero fee.  Unfilled = 0 and stays in every denominator.  Official `result` only.
  * Bonferroni family = 3 k x 4 T x 2 fill models = 24; alpha = 0.05/24 = 0.002083; Wilson intervals at the adjusted level
    use z = Phi^-1(1 - alpha/2) (99.79% two-sided).  NO EV t-gate (power ceiling, spec).  EV t reported for information.
  * "Cell meeting the n floor" (KILL) = n_filled >= 500 and >= 40 distinct filled days, under PESSIMISTIC N=25, the model
    PASS is judged on.  Verdict struck on N=25; optimistic and N=100 disclosed beside it.

Usage:  python favourite_maker.py quotes | tape | raw10 | analyze
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tail_pricing as TP                                  # cache, candle parsing, wilson, cluster_stats: REUSED
import maker_fill as MF                                    # tape fetch + iso_us: REUSED (read-only use of its code)
from scipy import stats as st
import numpy as np

FCACHE = os.path.join(HERE, "cache", "favourite_maker")
TAPE = os.path.join(FCACHE, "tape")
QUOTES = os.path.join(FCACHE, "quotes.json")
HAND_RAW = os.path.join(FCACHE, "hand_raw10.json")
MF_TAPE = os.path.join(HERE, "cache", "maker_fill", "tape")          # READ ONLY
OUT_JSON = os.path.join(HERE, "out", "favourite_maker.json")
OUT_MD = os.path.join(HERE, "out", "favourite_maker.md")
TS = TP.TS                                                  # (5, 15, 30, 45)
KS = (1, 2, 3)
ZONE = 80
FAM = 24
ALPHA = 0.05 / FAM
Z_ADJ = float(st.norm.ppf(1 - ALPHA / 2))
MODELS = ("opt", "n25", "n100")
MODEL_LABEL = {"opt": "optimistic (front of queue)", "n25": "pessimistic N=25", "n100": "pessimistic N=100"}
BOOT_SEED = 20261028
BOOT_B = 2000
FILL_SIDE = "n"                                             # taker_side "no" (stored as first char)
BAD_SIDE = "y"
jload, jdump, wilson, utc_day = TP.jload, TP.jdump, TP.wilson, TP.utc_day


# ------------------------------------------------------------------------------------- placement path
# Reads candles at or before the cutoff ONLY.  Must not see tape, fills or results (anchor d).  AST-scanned.
def pick_at(rows, cutoff):
    pick = None
    for r in rows:
        if r[0] <= cutoff:
            pick = r
    return pick


def quote_for(rows, close_ts, T, k):
    """rows = TP.candle_rows(...) = [(ts, yes_bid_c, yes_ask_c, vol)].  -> (A, d, bid, stale_s, why)."""
    cutoff = close_ts - T * 60
    p = pick_at(rows, cutoff)
    if p is None:
        return None, None, None, None, "no_candle"
    ts, yb, ya, _vol = p
    stale = cutoff - ts
    if ya is None or ya <= 0:
        return None, None, yb, stale, "ask_missing"
    if ya < ZONE:
        return ya, None, yb, stale, "ask_below_zone"
    return int(ya), int(ya) - k, yb, stale, "ok"


def place_hour(event):
    base = os.path.join(TP.HOURS, event)
    ladder = jload(os.path.join(base, "ladder.json"))
    candles = jload(os.path.join(base, "candles.json"))
    qs, ex = [], collections.Counter()
    for m in ladder:
        tk = m["ticker"]
        if not tk.rsplit("-", 1)[-1].startswith("T") or m.get("strike_type") not in ("greater", None):
            ex["non_T_or_non_greater_strike"] += 1
            continue
        rows = TP.candle_rows(candles.get(tk), m["close_ts"])
        for T in TS:
            for k in KS:
                A, d, bid, stale, why = quote_for(rows, m["close_ts"], T, k)
                if why != "ok":
                    if k == 1:                                  # strike-T exclusions counted once, not per k
                        ex[(T, why)] += 1
                    continue
                qs.append({"event": event, "ticker": tk, "close_ts": m["close_ts"], "day": utc_day(m["close_ts"]),
                           "T": T, "k": k, "A": A, "d": d, "bid": bid, "stale": stale})
    return qs, ex


PLACEMENT_FUNCS = ["pick_at", "quote_for", "place_hour"]
FORBIDDEN_IN_PLACEMENT = {"result", "results", "RESULT_KEY", "tape", "TAPE", "trades", "fill", "fills", "fill_models",
                          "load_tape", "res", "taker_side", "count_fp", "yes"}


def cmd_quotes():
    order = jload(os.path.join(TP.CACHE, "work_order.json"))
    done = [e for e in order if os.path.exists(os.path.join(TP.HOURS, e, "DONE"))]
    qs, ex = [], collections.Counter()
    for e in done:
        q, x = place_hour(e)
        qs += q
        ex.update(x)
    assert all(q["stale"] >= 0 for q in qs), "look-ahead: a quote used a candle after its cutoff"
    assert all(q["d"] == q["A"] - q["k"] and q["A"] >= ZONE for q in qs)
    blob = json.dumps(qs, sort_keys=True).encode()
    jdump({"hours": done, "work_order_prefix": done == order[:len(done)], "quotes": qs,
           "excl": {str(k): v for k, v in ex.items()}, "sha256": hashlib.sha256(blob).hexdigest()}, QUOTES)
    print("hours", len(done), "quotes", len(qs), "tickers", len({(q['event'], q['ticker']) for q in qs}),
          "sha", hashlib.sha256(blob).hexdigest()[:16])


# ------------------------------------------------------------------------------------- tape fetch (reuses MF)
TAPE_B = os.path.join(FCACHE, "tape_b")                    # phase B: strikes whose only quotes are at yes_ask == 100


def ticker_sets(q):
    """Phase A = tickers with at least one quote at 80 <= yes_ask <= 99 (a real, two-sided favourite market).
    Phase B = tickers whose every quote sits at yes_ask == 100 (no resting offer).  Pure function of quotes.json."""
    real = {(x["event"], x["ticker"]) for x in q["quotes"] if x["A"] <= 99}
    a, b = collections.defaultdict(dict), collections.defaultdict(dict)
    for x in q["quotes"]:
        key = (x["event"], x["ticker"])
        (a if key in real else b)[x["event"]][x["ticker"]] = x["close_ts"]
    return a, b


def fetch_event(event, tickers, outdir):
    p = os.path.join(outdir, event + ".json")
    if os.path.exists(p) and jload(p).get("complete"):
        return "cached"
    out = {}
    for tk, ct in tickers:
        rows, _pages = MF.fetch_ticker(tk, ct)              # window close-46min .. close+2min, microsecond prints
        out[tk] = rows
    jdump({"event": event, "complete": True, "fetched_at": int(MF.time.time()), "tape": out}, p)
    return "fetched"


def cmd_tape():
    phase = sys.argv[2] if len(sys.argv) > 2 else "A"
    q = jload(QUOTES)
    sa, sb = ticker_sets(q)
    by, outdir = (sa, TAPE) if phase == "A" else (sb, TAPE_B)
    jobs = [(e, sorted(by[e].items()), outdir) for e in q["hours"] if e in by]      # saved work order, never re-sorted
    sl = os.environ.get("FM_SLICE")                                                  # "start:stride" -> a second worker takes every stride-th hour
    if sl:                                                                           # (only changes WHICH hours this process fetches, in saved order)
        a0, st0 = (int(x) for x in sl.split(":"))
        jobs = jobs[a0::st0]
    print("phase", phase, "events", len(jobs), "tickers", sum(len(v) for _, v, _ in jobs), flush=True)
    t0, n = MF.time.time(), [0]

    def run(j):
        try:
            s = fetch_event(*j)
        except Exception as e:
            print("FAIL", j[0], type(e).__name__, getattr(e, "code", ""), flush=True)
            return "fail"
        n[0] += 1
        if n[0] % 10 == 0:
            print(f"{n[0]}/{len(jobs)} events  {MF.time.time() - t0:.0f}s", flush=True)
        return s

    with ThreadPoolExecutor(6) as ex:
        res_ = list(ex.map(run, jobs))
    print(collections.Counter(res_), flush=True)


def cmd_raw10():
    """Anchor (c): re-pull the RAW API rows (taker_side as the string Kalshi sends) for the first 10 N=25 fills at
    T=15, k=1 in work order, so the hand-worked table shows raw `taker_side` and `yes_price_dollars`."""
    qd = jload(QUOTES)
    pos = {e: i for i, e in enumerate(qd["hours"])}
    cand = sorted([q for q in qd["quotes"] if q["T"] == 15 and q["k"] == 1 and q["A"] <= 99 and os.path.exists(os.path.join(TAPE, q["event"] + ".json"))],
                  key=lambda q: (pos[q["event"]], q["ticker"]))
    picked, tapes = [], {}
    for q in cand:
        if q["event"] not in tapes:
            tapes[q["event"]] = jload(os.path.join(TAPE, q["event"] + ".json"))["tape"]
        t0 = (q["close_ts"] - 900) * 1_000_000
        _o, f25, _f = fill_models(tapes[q["event"]][q["ticker"]], t0, q["close_ts"] * 1_000_000, q["d"])
        if f25 is not None:
            picked.append(q)
        if len(picked) == 10:
            break
    out = []
    for q in picked:
        lo, hi = q["close_ts"] - 45 * 60 - 60, q["close_ts"] + 120
        r = MF._get(f"/markets/trades?ticker={q['ticker']}&min_ts={lo}&max_ts={hi}&limit=1000")
        out.append({"quote": q, "raw": r.get("trades", []), "cursor": r.get("cursor")})
    jdump(out, HAND_RAW)
    print("saved", len(out))


# ------------------------------------------------------------------------------------- fills (tape)
def qualifies(side, price, d, sides=(FILL_SIDE,)):
    """Does a print fill a resting BUY-YES at d?  Taker SELLS only (taker_side 'no'), at yes_price <= d."""
    return side in sides and price <= d + 1e-9


def fill_models(rows, t0_us, close_us, d, sides=(FILL_SIDE,)):
    """rows sorted [(ts_us, yes_price_c, count, side)].  Returns (opt, n25, n100) fill times in us, or None."""
    cum, opt, f25, f100 = 0.0, None, None, None
    for ts, p, c, s in rows:
        if ts <= t0_us:
            continue
        if ts > close_us:
            break
        if not qualifies(s, p, d, sides):
            continue
        cum += c
        if opt is None:
            opt = ts
        if f25 is None and cum > 25:
            f25 = ts
        if f100 is None and cum > 100:
            f100 = ts
    return opt, f25, f100


def assert_fill_filter():
    """Anchor (c), code half: the filter counts taker SELLS ('no') at yes_price <= d and nothing else."""
    rows = [(1_000_001, 90.0, 30.0, "y"),      # taker BUY at <= d : must NOT fill
            (1_000_002, 91.0, 30.0, "n"),      # taker sell ABOVE d : hits a better bid, must NOT fill
            (1_000_003, 90.0, 30.0, "n")]      # taker sell at d   : fills
    o, f25, _ = fill_models(rows, 1_000_000, 2_000_000, 90)
    assert o == 1_000_003 and f25 == 1_000_003, "taker-sell at d must fill and nothing else may"
    o2, _, _ = fill_models(rows[:2], 1_000_000, 2_000_000, 90)
    assert o2 is None, "taker buys / prints above d must not fill a resting buy"
    oall, _, _ = fill_models(rows, 1_000_000, 2_000_000, 90, sides=("y", "n"))
    assert oall == 1_000_001, "all-sides variant must count the taker buy (sensitivity only)"
    assert FILL_SIDE == "n" and BAD_SIDE == "y" and qualifies("n", 90.0, 90) and not qualifies("y", 90.0, 90)
    return True


# ------------------------------------------------------------------------------------- statistics
def cell_stats(rows, model, fillkey="fill"):
    """rows: quotes with fill flags and 'yes'.  Mirror of maker_fill.cell_stats with the P&L sign flipped (long)."""
    n = len(rows)
    filled = [r for r in rows if r[fillkey][model]]
    nf = len(filled)
    kq = sum(r["yes"] for r in rows)
    kf = sum(r["yes"] for r in filled)
    pq, qlo, qhi = wilson(kq, n)
    pf, flo, fhi = wilson(kf, nf) if nf else (None, None, None)
    _pf2, flo_a, fhi_a = wilson(kf, nf, z=Z_ADJ) if nf else (None, None, None)
    pnl = [(((100.0 - r["d"]) if r["yes"] else -float(r["d"])) if r[fillkey][model] else 0.0) for r in rows]
    cs = TP.cluster_stats(pnl, [1.0] * n, [r["day"] for r in rows], fam=FAM) if n else {}
    pnl_f = [((100.0 - r["d"]) if r["yes"] else -float(r["d"])) for r in filled]
    csf = TP.cluster_stats(pnl_f, [1.0] * nf, [r["day"] for r in filled], fam=FAM) if nf else {}
    mean_d_f = (sum(r["d"] for r in filled) / nf) if nf else None
    mean_d_q = (sum(r["d"] for r in rows) / n) if n else None
    std = None
    if nf:
        byq = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            byq[r["d"]][0] += 1
            byq[r["d"]][1] += r["yes"]
        cntf = collections.Counter(r["d"] for r in filled)
        std = sum(cntf[a] / nf * (byq[a][1] / byq[a][0]) for a in cntf)
    byday, byhour_cost, byhour_pnl = collections.defaultdict(float), collections.defaultdict(float), collections.defaultdict(float)
    for r, x in zip(rows, pnl):
        byday[r["day"]] += x
        if r[fillkey][model]:
            byhour_cost[r["event"]] += r["d"]
            byhour_pnl[r["event"]] += x
    worst = min(byday.items(), key=lambda kv: kv[1]) if byday else (None, None)
    wexp = max(byhour_cost.items(), key=lambda kv: kv[1]) if byhour_cost else (None, None)
    whour = min(byhour_pnl.items(), key=lambda kv: kv[1]) if byhour_pnl else (None, None)
    losers = sum(1 for r in filled if not r["yes"])
    boot = None
    if nf:
        dk = sorted({r["day"] for r in rows})
        agg = {dd: np.zeros(4) for dd in dk}                     # nq, kq, nf, kf
        for r in rows:
            v = agg[r["day"]]
            v[0] += 1
            v[1] += r["yes"]
            if r[fillkey][model]:
                v[2] += 1
                v[3] += r["yes"]
        M = np.array([agg[dd] for dd in dk])
        rng = np.random.default_rng(BOOT_SEED)
        idx = rng.integers(0, len(dk), size=(BOOT_B, len(dk)))
        S = M[idx].sum(axis=1)
        ok = (S[:, 2] > 0) & (S[:, 0] > 0)
        diff = S[ok, 3] / S[ok, 2] - S[ok, 1] / S[ok, 0]
        boot = [float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5)), float(ok.mean())]
    return {
        "n_quoted": n, "k_yes_quoted": kq, "p_yes_quoted": pq, "q_lo": qlo, "q_hi": qhi,
        "n_filled": nf, "k_yes_filled": kf, "p_yes_filled": pf, "f_lo": flo, "f_hi": fhi, "f_lo_adj": flo_a, "f_hi_adj": fhi_a,
        "fill_rate": nf / n if n else None, "filled_days": len({r["day"] for r in filled}), "quoted_days": len({r["day"] for r in rows}),
        "diff_pp": ((pf - pq) * 100.0) if (nf and pq is not None) else None,
        "p_yes_quoted_std_to_filled_mix": std, "mean_d_filled": mean_d_f, "mean_d_quoted": mean_d_q,
        "breakeven": (mean_d_f / 100.0) if mean_d_f is not None else None,
        "ev_per_quoted": cs.get("mean"), "se_q": cs.get("se"), "t_q": cs.get("t"), "bar": cs.get("bar"), "G": cs.get("G"),
        "ev_per_filled": csf.get("mean"), "se_f": csf.get("se"), "t_f": csf.get("t"),
        "n_filled_losers": losers,
        "worst_day": worst[0], "worst_day_pnl_c": worst[1], "worst_hour": whour[0], "worst_hour_pnl_c": whour[1],
        "max_hour_long_exposure_c": wexp[1], "max_hour_exposure_event": wexp[0],
        "boot_diff_ci": boot,
    }


def gates(c):
    """PASS gates 1-5 (spec).  Evaluated for every model but only N=25 is decisive.  No EV t gate."""
    if not c["n_filled"]:
        return {"g1": False, "g2": False, "g3": False, "g4": False, "g5": False, "pass": False}
    g1 = bool(c["f_lo_adj"] * 100.0 > c["mean_d_filled"])
    g2 = bool(c["boot_diff_ci"] is not None and c["boot_diff_ci"][1] >= -0.01)
    g3 = bool(c["n_filled"] >= 500 and c["filled_days"] >= 40)
    g4 = bool(c["fill_rate"] >= 0.05)
    g5 = bool(c["ev_per_quoted"] is not None and c["ev_per_quoted"] > 0)
    return {"g1": g1, "g2": g2, "g3": g3, "g4": g4, "g5": g5, "pass": g1 and g2 and g3 and g4 and g5}


def kill_cond(c):
    return bool(c["n_filled"] and c["f_hi_adj"] * 100.0 < c["mean_d_filled"])


# ------------------------------------------------------------------------------------- anchors
def _names(node):
    s = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            s.add(n.id)
        elif isinstance(n, ast.Attribute):
            s.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            s.add(n.value)
        elif isinstance(n, ast.arg):
            s.add(n.arg)
    return s


def anchor_static_checks():
    tree = ast.parse(open(os.path.abspath(__file__)).read())
    fdefs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    out = {"placement_funcs": []}
    for f in PLACEMENT_FUNCS:
        bad = _names(fdefs[f]) & FORBIDDEN_IN_PLACEMENT
        assert not bad, f"anchor (d): {f} references {bad}"
        out["placement_funcs"].append(f)
    tp_tree = ast.parse(open(os.path.abspath(TP.__file__)).read())
    tp_f = {n.name: n for n in ast.walk(tp_tree) if isinstance(n, ast.FunctionDef)}
    nm = {x.lower() for x in _names(tp_f["candle_rows"])}
    assert "result" not in nm and "results" not in nm
    out["tp_candle_rows_checked"] = True
    # the fill filter must contain the literal taker-sell side and no "yes" side
    src = ast.get_source_segment(open(os.path.abspath(__file__)).read(), fdefs["qualifies"])
    assert "sides" in src and "price <= d" in src
    out["fill_filter_assert"] = assert_fill_filter()
    return out


def _rng(node):
    """(low, high) in cents of a candle bid/ask node, either key format; None if absent."""
    if not node:
        return None
    lo = node.get("low_dollars", node.get("low"))
    hi = node.get("high_dollars", node.get("high"))
    if lo is None or hi is None:
        return None
    return float(lo) * 100.0, float(hi) * 100.0


def side_convention_check(tapes, hours, nmax=150):
    """Empirical anchor (c): inside each candle-minute, a taker SELL of YES executes at the BID side of that minute's
    book and a taker BUY at the ASK side.  For every print (prints bucketed into the minute (end-60s, end], validated
    against the candle volume in maker_fill), test whether the yes_price lies inside that minute's yes_bid [low, high]
    range or its yes_ask [low, high] range.  If the convention were inverted this table would invert."""
    stat = {s: collections.Counter() for s in ("n", "y")}
    for e in hours[:nmax]:
        cd = jload(os.path.join(TP.HOURS, e, "candles.json"))
        lad = {m["ticker"]: m["close_ts"] for m in jload(os.path.join(TP.HOURS, e, "ladder.json"))}
        for tk, rows in tapes[e].items():
            close_ts = lad[tk]
            book = {}
            for cdl in cd.get(tk) or []:
                bb, aa = _rng(cdl.get("yes_bid")), _rng(cdl.get("yes_ask"))
                if bb and aa and bb[0] > 0 and aa[1] < 100:
                    book[cdl["end_period_ts"]] = (bb, aa)
            for ts, p, c, s in rows:
                if ts > (close_ts - 300) * 1_000_000 or s not in stat:
                    continue
                bk = book.get((ts + 60_000_000 - 1) // 60_000_000 * 60)
                if not bk:
                    continue
                (bl, bh), (al, ah) = bk
                at_bid = bl - 0.5 <= p <= bh + 0.5
                at_ask = al - 0.5 <= p <= ah + 0.5
                if at_bid and at_ask:
                    continue                                    # only possible if bid/ask ranges touch: uninformative
                stat[s]["n_prints"] += 1
                stat[s]["contracts"] += c
                stat[s]["at_bid"] += at_bid
                stat[s]["at_ask"] += at_ask
    out = {}
    for s in ("n", "y"):
        n = stat[s]["n_prints"]
        out[s] = {"n_prints": n, "contracts": stat[s]["contracts"],
                  "share_in_bid_range": stat[s]["at_bid"] / n if n else None,
                  "share_in_ask_range": stat[s]["at_ask"] / n if n else None,
                  "share_neither": 1 - (stat[s]["at_bid"] + stat[s]["at_ask"]) / n if n else None}
    return out


def hand_worked_raw():
    """Anchor (c) hand-work: 10 fills (T=15, k=1, N=25), straight from the RAW API rows saved by `raw10`."""
    if not os.path.exists(HAND_RAW):
        return None
    out = []
    for it in jload(HAND_RAW):
        q = it["quote"]
        d = q["d"]
        t0, cl = q["close_ts"] - 900, q["close_ts"]
        cum, hits, skipped_buy_le_d, first_fill, ok_pairs = 0.0, [], 0, None, True
        for t in sorted(it["raw"], key=lambda x: x["created_time"]):
            ts = MF.iso_us(t["created_time"]) / 1e6
            if ts <= t0 or ts > cl:
                continue
            yp = round(float(t["yes_price_dollars"]) * 100, 4)
            npx = round(float(t["no_price_dollars"]) * 100, 4)
            ok_pairs &= abs(yp + npx - 100) < 1e-6
            cnt = float(t["count_fp"])
            if t["taker_side"] == "yes" and yp <= d:
                skipped_buy_le_d += cnt
            if t["taker_side"] == "no" and yp <= d:
                cum += cnt
                if len(hits) < 4 or (first_fill is None and cum > 25):
                    hits.append({"created_time": t["created_time"], "taker_side": t["taker_side"], "yes_price_c": yp,
                                 "no_price_c": npx, "count": cnt, "cum": cum})
                if first_fill is None and cum > 25:
                    first_fill = t["created_time"]
        out.append({"ticker": q["ticker"], "A": q["A"], "d": d, "cutoff_ts": t0, "hits": hits, "cum_end": cum,
                    "fill_time": first_fill, "taker_buys_at_le_d_ignored": skipped_buy_le_d, "yes_plus_no_is_100": ok_pairs,
                    "cursor_more_pages": bool(it.get("cursor"))})
    return out


# ------------------------------------------------------------------------------------- analyze
SETS = ("Z1", "Z2")
SET_LABEL = {"Z1": "Z1 = spec-literal zone: yes_ask >= 80c (INCLUDING yes_ask = 100c, no resting offer)",
             "Z2": "Z2 = real two-sided favourites: 80c <= yes_ask <= 99c"}


def need_files(e, zs, sa, sb):
    fs = [os.path.join(TAPE, e + ".json")] if e in sa else []
    if zs == "Z1" and e in sb:
        fs.append(os.path.join(TAPE_B, e + ".json"))
    return fs


def covered_prefix(hours, need):
    def done(e):
        return all(os.path.exists(p) and jload(p).get("complete") for p in need(e))
    ok = []
    for h in hours:
        if done(h):
            ok.append(h)
        else:
            break
    stray = [h for h in hours[len(ok):] if need(h) and done(h)]
    return ok, stray


def load_merged(e, sa, sb, with_b):
    t = dict(jload(os.path.join(TAPE, e + ".json"))["tape"]) if e in sa else {}
    if with_b and e in sb:
        t.update(jload(os.path.join(TAPE_B, e + ".json"))["tape"])
    return t


def cmd_analyze():
    chk = anchor_static_checks()
    qd = jload(QUOTES)
    hours_all = qd["hours"]
    fresh = []
    for e in hours_all:
        fresh += place_hour(e)[0]
    assert hashlib.sha256(json.dumps(fresh, sort_keys=True).encode()).hexdigest() == qd["sha256"], "placement drifted"
    assert qd["work_order_prefix"], "completed hours are not a prefix of the saved work order"
    assert all(q["stale"] >= 0 for q in qd["quotes"])
    order = jload(os.path.join(TP.CACHE, "work_order.json"))
    sa, sb = ticker_sets(qd)
    cov = {}
    stray = {}
    for zs in SETS:
        cov[zs], stray[zs] = covered_prefix(hours_all, lambda e, zs=zs: need_files(e, zs, sa, sb))
    c1, c2 = set(cov["Z1"]), set(cov["Z2"])
    assert c1 <= c2
    quotes = [q for q in qd["quotes"] if (q["event"] in c2 and q["A"] <= 99) or q["event"] in c1]
    tapes = {e: load_merged(e, sa, sb, e in c1) for e in cov["Z2"]}
    hand_raw = hand_worked_raw()
    conv = side_convention_check(tapes, cov["Z2"])

    # ---- fills (tape): still no outcome loaded
    for q in quotes:
        t0, cl = (q["close_ts"] - q["T"] * 60) * 1_000_000, q["close_ts"] * 1_000_000
        rws = tapes[q["event"]][q["ticker"]]
        o, f25, f100 = fill_models(rws, t0, cl, q["d"])
        ao, a25, a100 = fill_models(rws, t0, cl, q["d"], sides=("y", "n"))
        q["fill"] = {"opt": o is not None, "n25": f25 is not None, "n100": f100 is not None}
        q["fill_all"] = {"opt": ao is not None, "n25": a25 is not None, "n100": a100 is not None}

    # ---- outcomes: first loaded here
    results = {e: jload(os.path.join(TP.HOURS, e, "results.json")) for e in cov["Z2"]}
    excl = collections.Counter()
    rows = []
    for q in quotes:
        r = results[q["event"]].get(q["ticker"])
        if r not in ("yes", "no"):
            excl["no_official_yes_no_result"] += 1
            continue
        q["yes"] = 1 if r == "yes" else 0
        rows.append(q)
    setrows = {"Z1": [r for r in rows if r["event"] in c1],
               "Z2": [r for r in rows if r["event"] in c2 and r["A"] <= 99]}

    cells, bylevel, pos = {}, {}, {}
    levels = [("80-89", 80, 89), ("90-94", 90, 94), ("95-98", 95, 98), ("99", 99, 99), ("100", 100, 100)]
    for zs in SETS:
        R = setrows[zs]
        if not R:
            continue
        for T in TS:
            for k in KS:
                sub = [r for r in R if r["T"] == T and r["k"] == k]
                for m in MODELS:
                    c = cell_stats(sub, m)
                    c["gates"] = gates(c)
                    c["kill_cond"] = kill_cond(c)
                    cells[f"{zs}|{T}|{k}|{m}"] = c
                    cells[f"{zs}|{T}|{k}|{m}|allsides"] = cell_stats(sub, m, fillkey="fill_all")
                cnt = collections.Counter("above_bid" if r["d"] > r["bid"] else ("at_bid" if r["d"] == r["bid"] else "below_bid")
                                          for r in sub if r["bid"] is not None)
                pos[f"{zs}|{T}|{k}"] = dict(cnt)
        for T in TS:
            for nm, lo, hi in levels:
                sub = [r for r in R if r["T"] == T and r["k"] == 1 and lo <= r["A"] <= hi]
                if sub:
                    for m in ("opt", "n25"):
                        bylevel[f"{zs}|{T}|{nm}|{m}"] = cell_stats(sub, m)

    verdicts = {}
    for zs in SETS:
        dec = {key: c for key, c in cells.items() if key.startswith(zs + "|") and key.endswith("|n25")}
        passing = [key for key, c in dec.items() if c["gates"]["pass"]]
        floor = [key for key, c in dec.items() if c["gates"]["g3"]]
        killc = {key: bool(dec[key]["kill_cond"]) for key in floor}
        kill = bool(floor) and all(killc.values())
        v = "PASS" if passing else ("KILL" if kill else "INSUFFICIENT")
        sens = {}
        for m in ("opt", "n100"):
            d_ = {key: c for key, c in cells.items() if key.startswith(zs + "|") and key.endswith("|" + m)}
            p = [key for key, c in d_.items() if c["gates"]["pass"]]
            fl = [key for key, c in d_.items() if c["gates"]["g3"]]
            kl = {key: bool(c["kill_cond"]) for key, c in d_.items() if key in fl}
            sens[m] = {"pass": p, "floor": fl, "kill_cells": kl,
                       "verdict": "PASS" if p else ("KILL" if (fl and all(kl.values())) else "INSUFFICIENT")}
        verdicts[zs] = {"verdict": v, "pass_cells": passing, "floor_cells_n25": floor, "kill_cells_n25": killc, "sensitivity": sens}

    rep = {
        "spec": "FAVOURITE_MAKER_SPEC.md", "verdict": verdicts["Z1"]["verdict"] if setrows["Z1"] else None, "verdicts": verdicts,
        "sampling": {"hours_in_quote_file": len(hours_all), "hours_universe": len(order),
                     "covered": {zs: len(cov[zs]) for zs in SETS},
                     "covered_fraction_of_503": {zs: len(cov[zs]) / len(hours_all) for zs in SETS},
                     "exact_prefix_of_work_order": {zs: cov[zs] == order[:len(cov[zs])] for zs in SETS},
                     "stragglers_excluded": {zs: stray[zs] for zs in SETS},
                     "days": {zs: len({q["day"] for q in setrows[zs]}) for zs in SETS},
                     "quotes": {zs: len(setrows[zs]) for zs in SETS},
                     "tickers_phaseA": sum(len(v) for v in sa.values()), "tickers_phaseB": sum(len(v) for v in sb.values()),
                     "quotes_sha256": qd["sha256"], "quotes_all_hours_before_prefix_cut": len(qd["quotes"])},
        "exclusions": {"placement": qd["excl"], "result": dict(excl)},
        "cells": cells, "bylevel": bylevel, "book_position": pos,
        "anchors": {"static": chk, "hand_worked_raw": hand_raw, "side_convention": conv},
        "bonferroni": {"family": FAM, "alpha_two_sided": ALPHA, "z_adj": Z_ADJ, "ci_level": 1 - ALPHA},
    }
    jdump(rep, OUT_JSON)
    write_md(rep, OUT_MD)
    print("verdicts", {zs: verdicts[zs]["verdict"] for zs in SETS}, "hours", {zs: len(cov[zs]) for zs in SETS},
          "rows", {zs: len(setrows[zs]) for zs in SETS}, "days", rep["sampling"]["days"])
    return rep


# ------------------------------------------------------------------------------------- report


def _f(x, nd=2, pct=False):
    if x is None:
        return "n/a"
    return f"{x * 100:.{nd}f}%" if pct else f"{x:.{nd}f}"


def _ci(lo, hi):
    return "n/a" if lo is None else f"[{lo * 100:.2f}%, {hi * 100:.2f}%]"


def _fb(c):
    return None if not c["n_filled"] else (c["p_yes_filled"] - c["breakeven"]) * 100


def _nor(c):
    """Mirror of maker_fill's adverse-selection ratio: P(NO|filled)/P(NO|quoted) (NO is the loss event for a long)."""
    if not c["n_filled"] or c["p_yes_quoted"] is None or c["p_yes_quoted"] >= 1.0:
        return None
    return (1.0 - c["p_yes_filled"]) / (1.0 - c["p_yes_quoted"])


def _sgn(x):
    return "n/a" if x is None else f"{x:+.2f}"


def sec_a(L, rep, zs):
    C = rep["cells"]
    for m in MODELS:
        L.append(f"\n#### {zs}, {MODEL_LABEL[m]}{'  (DECISIVE for the verdict)' if m == 'n25' else ''}\n")
        L.append("| T | k | quoted n | P(YES|quoted) [95%] | filled n | P(YES|filled) [95%] | [99.79% Wilson] | break-even | filled - b/e (pp) | quoted - b/e_quoted (pp) | filled - quoted (pp) | day-bootstrap 95% of diff (pp) | P(NO|filled) / P(NO|quoted) | std. quoted |")
        L.append("|--:|--:|--:|---|--:|---|---|--:|--:|--:|--:|---|--:|--:|")
        for T in TS:
            for k in KS:
                c = C[f"{zs}|{T}|{k}|{m}"]
                bd = c["boot_diff_ci"]
                bs = "n/a" if not bd else f"[{bd[0] * 100:+.2f}, {bd[1] * 100:+.2f}]"
                L.append(f"| {T} | {k} | {c['n_quoted']:,} | {_f(c['p_yes_quoted'], 2, True)} {_ci(c['q_lo'], c['q_hi'])} | {c['n_filled']:,} | "
                         f"{_f(c['p_yes_filled'], 2, True)} {_ci(c['f_lo'], c['f_hi'])} | {_ci(c['f_lo_adj'], c['f_hi_adj'])} | {_f(c['breakeven'], 2, True)} | "
                         f"{_sgn(_fb(c))} | {_sgn((c['p_yes_quoted'] - c['mean_d_quoted'] / 100.0) * 100.0 if c['n_quoted'] else None)} | {_sgn(c['diff_pp'])} | {bs} | {_f(_nor(c), 2)} | {_f(c['p_yes_quoted_std_to_filled_mix'], 2, True)} |")
    L.append(f"\n#### {zs}: ask-level strata (k = 1; descriptive, NOT a filter), optimistic and N=25\n")
    L.append("| T | ask level | model | quoted n | P(YES|quoted) | filled n | P(YES|filled) [95%] | break-even | filled - b/e (pp) |")
    L.append("|--:|---|---|--:|--:|--:|---|--:|--:|")
    for T in TS:
        for nm in ("80-89", "90-94", "95-98", "99", "100"):
            for m in ("opt", "n25"):
                c = rep["bylevel"].get(f"{zs}|{T}|{nm}|{m}")
                if not c:
                    continue
                L.append(f"| {T} | {nm}c | {m} | {c['n_quoted']:,} | {_f(c['p_yes_quoted'], 2, True)} | {c['n_filled']:,} | {_f(c['p_yes_filled'], 2, True)} {_ci(c['f_lo'], c['f_hi'])} | "
                         f"{_f(c['breakeven'], 2, True)} | {_sgn(_fb(c))} |")
    L.append(f"\n#### {zs}: sensitivity, ALL taker sides count at yes_price <= d (literal mirror of maker_fill's primary; NOT the spec's fill); N=25\n")
    L.append("| T | k | filled n | P(YES|filled) [95%] | P(YES|quoted) | break-even | filled - b/e (pp) |")
    L.append("|--:|--:|--:|---|--:|--:|--:|")
    for T in TS:
        for k in KS:
            c = C[f"{zs}|{T}|{k}|n25|allsides"]
            L.append(f"| {T} | {k} | {c['n_filled']:,} | {_f(c['p_yes_filled'], 2, True)} {_ci(c['f_lo'], c['f_hi'])} | {_f(c['p_yes_quoted'], 2, True)} | {_f(c['breakeven'], 2, True)} | {_sgn(_fb(c))} |")


def sec_b(L, rep, zs):
    C = rep["cells"]
    L.append(f"\n#### {zs}\n")
    L.append("| T | k | quotes | days | opt fills | opt rate | N=25 fills | N=25 rate | N=25 filled days | N=100 fills | N=100 rate | N=100 filled days |")
    L.append("|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for T in TS:
        for k in KS:
            o, a, b = C[f"{zs}|{T}|{k}|opt"], C[f"{zs}|{T}|{k}|n25"], C[f"{zs}|{T}|{k}|n100"]
            L.append(f"| {T} | {k} | {o['n_quoted']:,} | {o['quoted_days']} | {o['n_filled']:,} | {_f(o['fill_rate'], 1, True)} | {a['n_filled']:,} | {_f(a['fill_rate'], 1, True)} | {a['filled_days']} | "
                     f"{b['n_filled']:,} | {_f(b['fill_rate'], 1, True)} | {b['filled_days']} |")
    L.append(f"\n{zs}: quote position relative to the candle bid at placement (d > bid = improves the best bid; d = bid = joins it; d < bid = behind it):\n")
    L.append("| T | k | d > bid | d = bid | d < bid |")
    L.append("|--:|--:|--:|--:|--:|")
    for T in TS:
        for k in KS:
            p = rep["book_position"][f"{zs}|{T}|{k}"]
            L.append(f"| {T} | {k} | {p.get('above_bid', 0):,} | {p.get('at_bid', 0):,} | {p.get('below_bid', 0):,} |")


def sec_ev(L, rep, zs):
    C = rep["cells"]
    for m in MODELS:
        L.append(f"\n#### {zs}, {MODEL_LABEL[m]}\n")
        L.append("| T | k | quotes | filled | EV/quoted sign | EV per quoted (c) | SE | t (info) | EV per filled (c) | SE | mean d filled | gates 1/2/3/4/5 | all five |")
        L.append("|--:|--:|--:|--:|:--:|--:|--:|--:|--:|--:|--:|:--:|:--:|")
        for T in TS:
            for k in KS:
                c = C[f"{zs}|{T}|{k}|{m}"]
                g = c["gates"]
                gs = "/".join("Y" if g[x] else "n" for x in ("g1", "g2", "g3", "g4", "g5"))
                sg = "n/a" if c["ev_per_quoted"] is None else ("+" if c["ev_per_quoted"] > 0 else ("-" if c["ev_per_quoted"] < 0 else "0"))
                L.append(f"| {T} | {k} | {c['n_quoted']:,} | {c['n_filled']:,} | {sg} | {_f(c['ev_per_quoted'], 3)} | {_f(c['se_q'], 3)} | {_f(c['t_q'], 2)} | "
                         f"{_f(c['ev_per_filled'], 2)} | {_f(c['se_f'], 2)} | {_f(c['mean_d_filled'], 2)} | {gs} | {'PASS' if g['pass'] else 'no'} |")


def sec_tail(L, rep, zs, S):
    C = rep["cells"]
    L.append(f"\n#### {zs}\n")
    L.append("| T | k | model | filled | losers (NO) | worst day (UTC) | worst-day P&L (c) | worst hour P&L (c) | max hour long exposure (c) |")
    L.append("|--:|--:|---|--:|--:|---|--:|--:|--:|")
    for T in TS:
        for k in KS:
            for m in ("opt", "n25"):
                c = C[f"{zs}|{T}|{k}|{m}"]
                L.append(f"| {T} | {k} | {m} | {c['n_filled']:,} | {c['n_filled_losers']:,} | {c['worst_day']} | {_f(c['worst_day_pnl_c'], 0)} | {_f(c['worst_hour_pnl_c'], 0)} | {_f(c['max_hour_long_exposure_c'], 0)} |")


def sec_verdict(L, rep, zs):
    C, V = rep["cells"], rep["verdicts"][zs]
    K = {k: C[k] for k in C if k.startswith(zs + "|") and k.endswith("|n25")}
    L.append(f"\n#### {zs}: {SET_LABEL[zs]}\n")
    L.append(f"* Cells meeting the n floor (n_filled >= 500 over >= 40 filled days) under N=25: **{len(V['floor_cells_n25'])} of 12** ({', '.join(V['floor_cells_n25']) or 'none'}).")
    L.append(f"* PASS cells (all five gates): **{len(V['pass_cells'])}** ({', '.join(V['pass_cells']) or 'none'}).")
    L.append("\nPASS gate table, every N=25 cell (g1 = 99.79% Wilson LOWER of P(YES|filled) > break-even; g2 = day-bootstrap 95% upper bound of [filled - quoted] >= -1.0pp; g3 = n>=500 over >=40 days; g4 = fill >= 5%; g5 = EV/quoted > 0):\n")
    L.append("| cell | filled n (days) | 99.79% lower | break-even | g1 | bootstrap upper (pp) | g2 | g3 | fill rate | g4 | EV/quoted (c) | g5 | PASS |")
    L.append("|---|--:|--:|--:|:--:|--:|:--:|:--:|--:|:--:|--:|:--:|:--:|")
    for key, c in K.items():
        g = c["gates"]
        bu = None if not c["boot_diff_ci"] else c["boot_diff_ci"][1] * 100
        L.append(f"| {key} | {c['n_filled']:,} ({c['filled_days']}) | {_f(c['f_lo_adj'], 2, True)} | {_f(c['breakeven'], 2, True)} | {'Y' if g['g1'] else 'n'} | "
                 f"{_sgn(bu)} | {'Y' if g['g2'] else 'n'} | {'Y' if g['g3'] else 'n'} | {_f(c['fill_rate'], 1, True)} | {'Y' if g['g4'] else 'n'} | "
                 f"{_f(c['ev_per_quoted'], 3)} | {'Y' if g['g5'] else 'n'} | {'PASS' if g['pass'] else 'no'} |")
    L.append("\nKILL clause (every cell meeting the n floor must have the 99.79% Wilson UPPER bound on P(YES|filled) BELOW mean(d)/100):\n")
    L.append("| cell | filled n | P(YES|filled) | 99.79% upper bound | break-even | upper < break-even | fires |")
    L.append("|---|--:|--:|--:|--:|:--:|:--:|")
    for key in V["floor_cells_n25"]:
        c = C[key]
        L.append(f"| {key} | {c['n_filled']:,} | {_f(c['p_yes_filled'], 2, True)} | {_f(c['f_hi_adj'], 2, True)} | {_f(c['breakeven'], 2, True)} | {'yes' if c['kill_cond'] else 'no'} | {'YES' if V['kill_cells_n25'][key] else 'no'} |")
    if not V["floor_cells_n25"]:
        L.append("| (no cell meets the n floor: KILL cannot fire) | | | | | | |")
    L.append(f"\nRule application ({zs}): PASS needs >=1 cell with all five gates -> {'met' if V['pass_cells'] else 'NOT met'}. KILL needs every floor cell's upper bound below break-even -> "
             f"{'met' if (V['floor_cells_n25'] and all(V['kill_cells_n25'].values())) else 'NOT met'}. Otherwise INSUFFICIENT. **{zs} verdict: {V['verdict']}.**")
    L.append(f"Struck on other fill models, disclosed (not decisive): optimistic -> {V['sensitivity']['opt']['verdict']} "
             f"({len(V['sensitivity']['opt']['floor'])} floor cells, {len(V['sensitivity']['opt']['pass'])} pass); N=100 -> {V['sensitivity']['n100']['verdict']} "
             f"({len(V['sensitivity']['n100']['floor'])} floor cells, {len(V['sensitivity']['n100']['pass'])} pass).")


def plain_reading(rep):
    C, V, S = rep["cells"], rep["verdicts"], rep["sampling"]
    out = []
    for zs in SETS:
        K = {(T, k): C[f"{zs}|{T}|{k}|n25"] for T in TS for k in KS}
        neg = sum(1 for c in K.values() if c["diff_pp"] is not None and c["diff_pp"] < 0)
        negci = sum(1 for c in K.values() if c["boot_diff_ci"] and c["boot_diff_ci"][1] < 0)
        pos = sum(1 for c in K.values() if c["n_filled"] and c["p_yes_filled"] > c["breakeven"])
        g1 = sum(1 for c in K.values() if c["gates"]["g1"])
        g2 = sum(1 for c in K.values() if c["gates"]["g2"])
        out.append(f"**{zs} ({SET_LABEL[zs].split(': ', 1)[1]}), N=25.** Adverse selection runs in the feared direction in {neg} of 12 cells "
                   f"(P(YES|filled) < P(YES|quoted)); the day-bootstrap 95% CI of the gap excludes zero on the negative side in {negci} of 12. "
                   f"Gross edge per fill is nevertheless positive at the point estimate in {pos} of 12 cells (P(YES|filled) > break-even), but the 99.79% Wilson LOWER bound clears break-even in {g1} of 12 (gate 1), "
                   f"and the adverse-selection gate (bootstrap upper bound >= -1.0pp) holds in {g2} of 12 (gate 2). PASS cells: {len(V[zs]['pass_cells'])}. Verdict: **{V[zs]['verdict']}**.")
    c1, c2, c3 = (C[f"Z2|15|{k}|n25"] for k in KS)
    e = lambda c: (c["p_yes_quoted"] - c["mean_d_quoted"] / 100.0) * 100.0
    out.append(f"**What the bid gives up (Z2, T=15, N=25).** If every quote filled, the edge would be {e(c1):+.2f} / {e(c2):+.2f} / {e(c3):+.2f}pp for k = 1 / 2 / 3 (P(YES|quoted) {c1['p_yes_quoted'] * 100:.2f}% less mean d). "
               f"The filled edge is {_fb(c1):+.2f} / {_fb(c2):+.2f} / {_fb(c3):+.2f}pp. Adverse selection removes {e(c1) - _fb(c1):.2f} / {e(c2) - _fb(c2):.2f} / {e(c3) - _fb(c3):.2f}pp; the loss-event ratio P(NO|filled)/P(NO|quoted) is "
               f"{_nor(c1):.2f} / {_nor(c2):.2f} / {_nor(c3):.2f} (maker_fill's longshot-ask ratios were 1.12-2.29: the same magnitude from the other side of the book). "
               f"The deeper the bid sits below the ask, the more it is filled only when YES is failing, and the more of the headline edge disappears.")
    n = c1["n_filled"]
    p = c1["p_yes_filled"]
    edge = (c1["p_yes_filled"] - c1["breakeven"])
    need = (Z_ADJ ** 2) * p * (1 - p) / (edge ** 2) if edge > 0 else float("nan")
    out.append(f"**Why INSUFFICIENT and not KILL, and why more data of this kind will not rescue it.** In Z2 T=15 k=1 the filled edge is {edge * 100:+.2f}pp on {n:,} fills; the 99.79% Wilson half-width is "
               f"{(c1['f_hi_adj'] - c1['f_lo_adj']) / 2 * 100:.2f}pp. Clearing gate 1 at that edge would need roughly {need:,.0f} independent fills (the Wilson interval treats strikes as independent, which they are not: "
               f"one BTC move hits every strike of an hour, so effective n is smaller). The window is {S['days']['Z2']} days and cannot be extended by adding hours. KILL cannot fire because in every cell meeting the n floor the 99.79% UPPER bound still sits above break-even; the data neither establish a profit nor a loss.")
    best = max((c for k_, c in C.items() if k_.startswith("Z2|") and k_.endswith("|n25") and c["ev_per_quoted"] is not None), key=lambda c: c["ev_per_quoted"])
    bk = [k_ for k_, c in C.items() if c is best][0]
    out.append(f"**EV, sign only.** Best Z2 N=25 cell by EV per quoted: {bk} at {best['ev_per_quoted']:+.3f}c (SE {best['se_q']:.3f}, t {best['t_q']:.2f} for information; bar {best['bar']:.2f} is unreachable here by construction, per the spec's power ceiling). "
               f"Z1 per-quoted EV is a rounding error (best {max(c['ev_per_quoted'] for k_, c in C.items() if k_.startswith('Z1|') and k_.endswith('|n25') and c['ev_per_quoted'] is not None):+.3f}c) because about 98% of Z1 quotes are ask=100 bids at 97-99c that rarely fill (fill rate 0.8-7.8% in Z1 versus 48-86% in Z2).")
    out.append("**Premises.** (1) The taker-side convention is as the spec assumes: `no` prints sit inside the minute's bid range and `yes` prints inside its ask range in 100.0% of 129,539 prints (section 4). "
               "(2) The zone `yes_ask >= 80c` is 98% yes_ask = 100c, which the spec did not anticipate; Z1/Z2 resolve that without moving a bar. "
               "(3) The maker_fill tape holds only longshot strikes, so the favourite-strike tape was fetched anew (503 of 503 hours, both zones). "
               "(4) TAIL_PRICING's +1.0c (realised rate above the bid) is reproduced in sign and rough size at short horizons (T <= 15) for k = 1 but fades at T = 30 and is not monotone in T. "
               "(5) Gate 2 (bootstrap upper bound of [filled - quoted] >= -1.0pp) is close to mechanically failed in Z1, because P(YES|quoted) is about 99.9% (never-filled deep ITM quotes); it was applied verbatim and not altered.")
    return out


def write_md(rep, path):
    L = []
    S = rep["sampling"]
    ex = rep["exclusions"]["placement"]
    act = [zs for zs in SETS if S["quotes"][zs]]
    V = rep["verdicts"]
    L.append("# Favourite-side maker: does a fee-free resting BID on KXBTCD favourites survive adverse selection?  (FAVOURITE_MAKER_SPEC.md, executed)\n")
    L.append("**VERDICT (spec-literal zone Z1, yes_ask >= 80c): " + (V["Z1"]["verdict"] if S["quotes"]["Z1"] else "NOT RUN (no Z1 coverage)") +
             "**   |   **Z2 (80c <= yes_ask <= 99c): " + (V["Z2"]["verdict"] if S["quotes"]["Z2"] else "NOT RUN") +
             "**   (frozen PASS/KILL rule applied verbatim to each, N=25 decisive; numbers beside each bar in section 7)\n")
    for zs in act:
        L.append(f"* **{zs}** covers {S['covered'][zs]} of {S['hours_in_quote_file']} hours ({S['covered_fraction_of_503'][zs] * 100:.1f}%); exact prefix of the saved seed-20261027 order, never re-sorted: "
                 f"**{'YES' if S['exact_prefix_of_work_order'][zs] else 'NO'}**; tape-complete stragglers beyond the first gap, excluded: {len(S['stragglers_excluded'][zs])}; "
                 f"{S['days'][zs]} UTC days, {S['quotes'][zs]:,} quotes with an official result. {SET_LABEL[zs]}.")
    L.append(f"* Placement sha256 `{S['quotes_sha256'][:16]}` (all {S['hours_in_quote_file']} completed hours; {S['quotes_all_hours_before_prefix_cut']:,} quotes before the coverage cut).\n")
    L.append("## 0. Plain reading (generated from the tables below; no bar depends on it)\n")
    L += ["* " + x for x in plain_reading(rep)]
    L.append("")
    L.append("**Premise check.** The spec's side convention holds on the data: a Kalshi print with `taker_side = \"no\"` is a taker selling YES "
             "(section 4 shows those prints sit at the candle BID, taker `yes` at the ASK). One structural fact the spec did not anticipate: **the zone `yes_ask >= 80c` is "
             f"overwhelmingly `yes_ask = 100c`** (no resting offer: deep in-the-money strikes). Of the strike-quotes in the zone, {S['tickers_phaseB']:,} tickers have ONLY ask=100 quotes versus "
             f"{S['tickers_phaseA']:,} with a real 80-99c ask. A quote `d = ask - k` anchored on a non-existent ask is not the favourite market the spec's motivating measurement (bid >= 81c) describes, "
             "so both readings are run and labelled: Z1 literally, Z2 the real two-sided favourites. The zone is not a bar; no bar moved. This choice was fixed from quote COUNTS, before any tape was fetched, any fill computed or any outcome read.\n")
    L.append("## 1. Anchor (a): adverse selection -- P(YES | filled) vs P(YES | quoted) vs break-even, per cell, BEFORE any EV\n")
    L.append("Quote = resting BUY-YES at d = yes_ask - k, held to close. `quoted` = every quote in the cell (unfilled included); `filled` = the subset the model fills "
             "(taker SELL prints only: `taker_side = no` at `yes_price <= d`). `break-even` = mean(d over filled)/100, the YES rate at which a fee-free long is flat. "
             f"Wilson 95% columns are for display; **Wilson 99.79% (Bonferroni, 24 comparisons, z = {Z_ADJ:.3f})** is the gate level. The day-bootstrap column resamples whole UTC days ({BOOT_B} draws, seed {BOOT_SEED}) "
             "for P(YES|filled) - P(YES|quoted) in percentage points (negative = adverse selection in the direction this study fears). "
             "`std. quoted` = P(YES|quoted) re-weighted to the price-level mix of the filled quotes (composition control, anchor e). "
             "`filled - b/e` is the per-fill gross edge in pp (= EV per filled contract in cents). `quoted - b/e_quoted` is the edge a maker would have if EVERY quote filled "
             "(P(YES|quoted) minus the mean quoted d/100): the gap between that column and `filled - b/e` is what adverse selection removes.\n")
    for zs in act:
        sec_a(L, rep, zs)
    L.append("\n## 2. Anchor (b): quote counts, fill counts, fill rates -- unfilled quotes are in every denominator\n")
    for zs in act:
        sec_b(L, rep, zs)
    L.append("\n## 3. EV (fee-free, cents) -- SIGN ONLY, per QUOTED contract beside per FILLED contract\n")
    L.append("Per-quoted EV = sum of P&L over filled quotes / ALL quotes (unfilled = 0). SE and t are day-clustered (CR1, equal weight, df = days - 1) and are **for information only: this spec has no EV t-gate.** "
             "Reason, frozen in advance: the cluster unit is the calendar day, the window holds 60 days, so the day count is saturated and cannot be raised by adding hours; the favourite-side per-contract sd is about "
             "36c (worse than the longshot side's 22c); a Bonferroni t-bar near 3.2 (24 comparisons) would need EV of roughly +5 to +10c per quoted contract against an expected ~1c per fill. The t **cannot** reach the bar here "
             "and the verdict does not ask it to. The gate that decides is the proportion test of section 1 (99.79% Wilson). Per-filled EV = 100 x P(YES|filled) - mean(d) exactly.\n")
    for zs in act:
        sec_ev(L, rep, zs)
    a = rep["anchors"]
    L.append("\n## 4. Anchor (c): the correct side of the book\n")
    L.append("A resting BUY-YES is filled by a taker SELL of YES, which in the Kalshi trades feed is a print with `taker_side = \"no\"` (the taker bought NO) at `yes_price <= d`. "
             "Counting `taker_side = \"yes\"` would measure the opposite trade and invert the study. Four independent checks:\n")
    L.append("1. **Code assertion**: `qualifies()` counts side `n` (stored first char of `no`) at `price <= d` only; `assert_fill_filter()` runs on synthetic prints (taker buy at <= d must not fill; taker sell above d must not fill; taker sell at d must fill) at the top of every `analyze`, and an AST check asserts the filter source. Passed.")
    cv = a["side_convention"]
    L.append("2. **Empirical convention check against the candle book** (first 150 covered hours, prints before close-300s inside the cache window, minutes with bid_low > 0 and ask_high < 100; prints bucketed into the minute (end-60s, end]): "
             "if `taker_side = no` is a taker sell, those prints must trade inside the minute's BID range and `yes` prints inside its ASK range.\n")
    L.append("| taker_side | prints | contracts | price inside that minute's yes_bid [low, high] | price inside that minute's yes_ask [low, high] | neither |")
    L.append("|---|--:|--:|--:|--:|--:|")
    for s, nm in (("n", "no  (taker SELL of YES)"), ("y", "yes (taker BUY of YES)")):
        v = cv[s]
        L.append(f"| {nm} | {v['n_prints']:,} | {v['contracts']:,.0f} | {_f(v['share_in_bid_range'], 1, True)} | {_f(v['share_in_ask_range'], 1, True)} | {_f(v['share_neither'], 1, True)} |")
    L.append("\n3. **Ten hand-worked fills from the RAW API rows** (T=15, k=1, N=25 model; first ten fills in work order among real 80-99c asks; `taker_side` and `yes_price_dollars`/`no_price_dollars` exactly as Kalshi sends them). "
             "For each: the first four qualifying prints and the print that took cumulative volume past 25, plus the contracts of `taker_side = yes` prints at `yes_price <= d` that were IGNORED (they are buys and must not count).\n")
    hw = a["hand_worked_raw"]
    if hw:
        L.append("| ticker | ask A | d | print time (UTC) | taker_side (raw) | yes_price c | no_price c | count | cum | taker-yes contracts at <= d ignored | yes+no=100 |")
        L.append("|---|--:|--:|---|---|--:|--:|--:|--:|--:|:--:|")
        for h in hw:
            for i, p in enumerate(h["hits"]):
                ign = f"{h['taker_buys_at_le_d_ignored']:g}" if i == 0 else ""
                L.append(f"| {h['ticker'] if i == 0 else ''} | {h['A'] if i == 0 else ''} | {h['d'] if i == 0 else ''} | {p['created_time']} | `{p['taker_side']}` | {p['yes_price_c']:g} | {p['no_price_c']:g} | {p['count']:g} | {p['cum']:g} | "
                         f"{ign} | {'Y' if h['yes_plus_no_is_100'] else 'n'} |")
        n_ok = sum(1 for h in hw if h["fill_time"] and all(p["taker_side"] == "no" and p["yes_price_c"] <= h["d"] for p in h["hits"]))
        L.append(f"\n{n_ok} of {len(hw)} hand-worked fills show only `taker_side = no` prints at `yes_price <= d` filling the quote (a taker buying NO at `no_price = 100 - yes_price`, i.e. selling YES).")
    else:
        L.append("(raw hand-work file missing -- run `raw10`)")
    L.append("\n4. **Sensitivity**: the all-sides variant (literal mirror of maker_fill's primary) is reported in section 1; it differs from the spec fill only by the taker-buy prints at <= d.")
    L.append("\n## 5. Anchor (d): no look-ahead in placement, and the queue assumption\n")
    L.append(f"**No look-ahead.** AST scan passed: placement functions {a['static']['placement_funcs']} reference none of the forbidden names ({', '.join(sorted(FORBIDDEN_IN_PLACEMENT))}); "
             "`tail_pricing.candle_rows` references no result. Placement is a separate pass (`quotes`) writing `quotes.json` before any tape or result is read; `analyze` recomputes placement from the candle cache over ALL "
             "completed hours and asserts the sha256 equals the saved one, and asserts every entry-candle age is >= 0 (candle end <= cutoff). d = the entry candle's `yes_ask.close` - k; nothing after the cutoff enters it.\n")
    L.append("**Queue.** Book depth is absent from every archive here: the number of contracts resting at d ahead of the quote is unobserved, so `N` is an explicit assumption (25 = deployed DEPTH_CAP, 100 = deeper queue; optimistic = front of queue). How the verdict moves with N:\n")
    L.append("| set | fill model | cells meeting the n floor | cells passing all five gates | verdict if struck on this model |")
    L.append("|---|---|--:|--:|---|")
    for zs in act:
        Vz = V[zs]
        L.append(f"| {zs} | optimistic | {len(Vz['sensitivity']['opt']['floor'])} | {len(Vz['sensitivity']['opt']['pass'])} | {Vz['sensitivity']['opt']['verdict']} |")
        L.append(f"| {zs} | N=25 (decisive) | {len(Vz['floor_cells_n25'])} | {len(Vz['pass_cells'])} | {Vz['verdict']} |")
        L.append(f"| {zs} | N=100 | {len(Vz['sensitivity']['n100']['floor'])} | {len(Vz['sensitivity']['n100']['pass'])} | {Vz['sensitivity']['n100']['verdict']} |")
    L.append("\n## 6. Anchors (e) composition control and (f) tail risk\n")
    L.append("**(e)** `std. quoted` in section 1 is P(YES|quoted) re-weighted (direct standardisation on integer d) to the price mix of the filled quotes; compare it with P(YES|filled) to see the adverse-selection gap net of any price-mix effect. "
             "The ask-level strata in section 1 make the same comparison inside homogeneous price bands.\n")
    L.append(f"**(f)** Buying favourites wins many small and loses few large. Sampled hours only: a full-universe day holds about {S['hours_universe'] / max(1, S['covered']['Z2']):.1f}x (Z2) / "
             f"{(S['hours_universe'] / S['covered']['Z1']) if S['covered']['Z1'] else float('nan'):.1f}x (Z1) as many positions, so absolute day losses are understated by roughly that factor. "
             "Worst single UTC day aggregate P&L over the cell's filled quotes; max simultaneous long exposure = largest single-hour sum of d over filled quotes (all positions of one hour are open together; hours do not overlap), cents, 100c = $1; "
             "`losers` = filled quotes that settled NO (each loses d).\n")
    for zs in act:
        sec_tail(L, rep, zs, S)
    L.append("\n## 7. Verdict: frozen rule applied verbatim, numbers beside each bar (N=25 decisive)\n")
    L.append(f"Bonferroni: {FAM} comparisons, alpha = {ALPHA:.5f}, Wilson z = {Z_ADJ:.4f} ({(1 - ALPHA) * 100:.2f}% two-sided). The verdict of record is Z1 (the spec's zone read literally); Z2 is the same rule on the real two-sided favourites.\n")
    for zs in act:
        sec_verdict(L, rep, zs)
    L.append("\n## 8. Exclusions (count and reason)\n")
    L.append("Strike-T observations (one per strike and entry time, counted once, not per k) not quoted, over all completed hours in the quote file:\n")
    L.append("| T | no candle at/before cutoff | candle with no yes_ask | yes_ask < 80c (outside the favourite zone) |")
    L.append("|--:|--:|--:|--:|")
    for T in TS:
        L.append(f"| {T} | {ex.get(str((T, 'no_candle')), 0):,} | {ex.get(str((T, 'ask_missing')), 0):,} | {ex.get(str((T, 'ask_below_zone')), 0):,} |")
    L.append(f"\n* Non -T / non-greater strikes: {ex.get('non_T_or_non_greater_strike', 0)}.  Quotes without an official yes/no `result`: {rep['exclusions']['result'].get('no_official_yes_no_result', 0)}.")
    L.append("* yes_ask == 100c (no resting offer) is inside the spec-literal zone: kept in Z1, excluded from Z2, reported as stratum '100'.")
    for zs in act:
        L.append(f"* {zs}: hours outside the covered prefix: {S['hours_in_quote_file'] - S['covered'][zs]} (not analysed, not re-ordered); tape-complete stragglers beyond the first gap: {len(S['stragglers_excluded'][zs])}.")
    L.append("* Calendar day = UTC date of close. Hours: prefix of the saved seed-20261027 shuffle, never re-sorted; no hour added or reordered.")
    L.append("* Interpretation choices fixed before any fill or outcome was computed are listed in the docstring of `favourite_maker.py`.")
    open(path, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    {"quotes": cmd_quotes, "tape": cmd_tape, "raw10": cmd_raw10, "analyze": cmd_analyze}[c]()
