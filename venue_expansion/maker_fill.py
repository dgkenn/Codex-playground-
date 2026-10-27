"""maker_fill.py -- executes MAKER_FILL_SPEC.md (registered 2026-10-27).  Nothing here may move a bar.

QUESTION. Resting a SELL-YES at a = yes_bid + k on Kalshi KXBTCD pays no maker fee.  Does the spread captured
survive ADVERSE SELECTION, i.e. is P(YES | filled) <= P(YES | quoted) + (what the spread pays for)?
PRIMARY MEASUREMENT = P(YES|filled) vs P(YES|quoted) per cell with Wilson 95% intervals (anchor a).  EV is secondary.

ANCHOR (f) -- WHY THIS MODULE FETCHES A TRADE TAPE.  The cached candles (cache/tail_pricing) are (i) TOTAL per-minute
volume with only a trade-price low/high/mean, so volume at price >= a is not identified (section F1 of the report
brackets it rigorously and shows the bracket is wide), and (ii) truncated at close-5min by the original fetch
(end_ts = close - min(TS)*60), so the final 5 minutes of "held to close" and the whole post-T window of T=5 are NOT in
the archive.  The HF TrevorJS/kalshi-trades archive ends 2026-01-30, before the universe window (2026-08-22..10-20).
The public Kalshi API `GET /markets/trades` carries every print (yes_price, count_fp, taker_side, microsecond
created_time) for the window, so price-conditional volume is MEASURED, not attributed.  The tape is fetched into
cache/maker_fill/tape/ for exactly the strikes the frozen placement rule quotes; no other hour is added.

FROZEN INTERPRETATION CHOICES (spec silent or ambiguous; fixed BEFORE any fill or outcome was computed):
  * Universe / hours: the 503 completed hours in cache/tail_pricing (prefix of the saved seed-20261027 work_order.json,
    never re-sorted), 60 UTC days.  Calendar day = UTC date of close = cluster unit.
  * Quote placement: tail_pricing.entry_quote() verbatim (last candle with end_period_ts <= close - T*60; yes_bid.close;
    bid 0 / no candle = untradeable, NOT quoted, counted).  a = b + k, k in {1,2,3}, quoted iff a <= 20 (cents).
    Strikes with a > 20 are NOT quoted (the cap); the spec sentence "above 20c is reported but cannot PASS" is read as
    "a > 20 is outside the placed universe": counted as an exclusion, not simulated.  1 contract per quote.
  * Quote lives from t0 = close - T*60 (exclusive) to close (inclusive).  No re-quote, no cancel.
  * Fill, evaluated on the TRADE TAPE: V(t) = cumulative count_fp of prints with created_time in (t0, close] and
    yes_price >= a, ALL taker sides (spec-literal "traded volume at a price >= a").
        OPTIMISTIC : filled iff V > 0 at any time.
        PESSIMISTIC: filled iff V > N at any time, N in {25, 100} (strictly exceeds; N is an ASSUMPTION, anchor d).
    Sensitivity variant (reported, never selected): same rules counting only taker_side == 'yes' prints (the prints that
    actually lifted offers).  Primary = all sides = spec-literal.
  * P&L per filled contract, zero fee: +a if result == 'no', -(100-a) if 'yes'.  Unfilled = 0 and stays in the
    denominator.  EV per quoted = sum(P&L)/n_quoted.  Official `result` only; others excluded with a count.
  * Bonferroni family = 3 k x 4 T x 2 fill models = 24; bar = Student-t quantile p = 1 - 0.05/24/2 on df = days-1.
    t is signed, day-clustered (CR1), equal weight, computed on the per-QUOTED series (unfilled = 0).
  * Gate 1 compares the Wilson 95% upper bound of P(YES|filled) with mean(a over the filled quotes)/100.
  * "Cell meeting the n floor" (used by KILL) = n_filled >= 500 and >= 40 distinct filled days (PASS gate 4), evaluated
    under the PESSIMISTIC N=25 model, the same model PASS is judged on.  KILL = every such cell has
    P(YES|filled) >= 2 x P(YES|quoted) AND Wilson(filled).lo > Wilson(quoted).hi.  If no cell meets the floor KILL
    cannot fire.  PASS needs >= 1 cell passing all five gates under N=25.  Else INSUFFICIENT.
  * Verdict is struck on N=25 only; N=100 and the optimistic bound are disclosed beside it (anchor d).

Usage:  python maker_fill.py quotes | tape | analyze
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import math
import os
import random
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tail_pricing as TP                                  # cache + parsing are REUSED, not re-implemented

MCACHE = os.path.join(HERE, "cache", "maker_fill")
TAPE = os.path.join(MCACHE, "tape")
QUOTES = os.path.join(MCACHE, "quotes.json")
OUT_JSON = os.path.join(HERE, "out", "maker_fill.json")
OUT_MD = os.path.join(HERE, "out", "maker_fill.md")
API = TP.API
TS = TP.TS                                                  # (5, 15, 30, 45)
KS = (1, 2, 3)
CAP = 20
NS = (25, 100)
FAM = 24
MODELS = ("opt", "n25", "n100")
MODEL_LABEL = {"opt": "optimistic (front of queue)", "n25": "pessimistic N=25", "n100": "pessimistic N=100"}
UA = "maker-fill-research/1.0"
BOOT_SEED = 20261028
BOOT_B = 2000

jload, jdump, wilson, utc_day = TP.jload, TP.jdump, TP.wilson, TP.utc_day


# ------------------------------------------------------------------------------------- placement path
# Everything in PLACEMENT_FUNCS reads candles at or before the cutoff ONLY.  It must not see the tape, fills, or
# results (anchor c).  Asserted by AST scan in anchor_static_checks().
def quote_for(raw_candles, close_ts, T, k):
    """-> (b, a, stale_s, why).  b = yes_bid close of the last candle with end <= close - T*60 (TP.entry_quote)."""
    b, why, _vol, stale = TP.entry_quote(raw_candles, close_ts, T)
    if b is None:
        return None, None, stale, why
    a = b + k
    if a > CAP:
        return b, None, stale, "a_gt_cap"
    return b, a, stale, "ok"


def place_hour(event):
    d = os.path.join(TP.HOURS, event)
    ladder = jload(os.path.join(d, "ladder.json"))
    candles = jload(os.path.join(d, "candles.json"))
    qs, ex = [], collections.Counter()
    for m in ladder:
        tk = m["ticker"]
        if not tk.rsplit("-", 1)[-1].startswith("T") or m.get("strike_type") not in ("greater", None):
            ex["non_T_or_non_greater_strike"] += 1
            continue
        for T in TS:
            for k in KS:
                b, a, stale, why = quote_for(candles.get(tk), m["close_ts"], T, k)
                if why != "ok":
                    ex[(T, k, why)] += 1
                    continue
                qs.append({"event": event, "ticker": tk, "close_ts": m["close_ts"], "day": utc_day(m["close_ts"]),
                           "T": T, "k": k, "b": b, "a": a, "stale": stale})
    return qs, ex


PLACEMENT_FUNCS = ["quote_for", "place_hour"]
FORBIDDEN_IN_PLACEMENT = {"result", "results", "RESULT_KEY", "tape", "TAPE", "trades", "fill", "fills", "fill_models",
                          "load_tape", "res"}


def cmd_quotes():
    order = jload(os.path.join(TP.CACHE, "work_order.json"))
    done = [e for e in order if os.path.exists(os.path.join(TP.HOURS, e, "DONE"))]
    qs, ex = [], collections.Counter()
    for e in done:
        q, x = place_hour(e)
        qs += q
        ex.update(x)
    assert all(q["stale"] >= 0 for q in qs), "look-ahead: a quote used a candle after its cutoff"
    blob = json.dumps(qs, sort_keys=True).encode()
    jdump({"hours": done, "quotes": qs, "excl": {str(k): v for k, v in ex.items()},
           "sha256": hashlib.sha256(blob).hexdigest()}, QUOTES)
    print("hours", len(done), "quotes", len(qs), "sha", hashlib.sha256(blob).hexdigest()[:16])


# ------------------------------------------------------------------------------------- tape fetch
_rl = threading.Lock()
_next = [0.0]


def _get(path, tries=14, gap=0.22):
    for i in range(tries):
        with _rl:                                           # global pacing across threads (~6 req/s)
            now = time.time()
            wait = _next[0] - now
            _next[0] = max(now, _next[0]) + gap
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as fh:
                return json.load(fh)
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (400, 404) or i == tries - 1:
                raise
            time.sleep(min(20, 1 + i))


def iso_us(s):
    """'2026-08-22T03:59:43.52957Z' -> integer microseconds since epoch (fractional part of any length)."""
    s = s.rstrip("Z")
    head, _, frac = s.partition(".")
    base = int(TP.dt.datetime.strptime(head, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=TP.dt.timezone.utc).timestamp())
    return base * 1_000_000 + int((frac + "000000")[:6])


def fetch_ticker(tk, close_ts):
    rows, cur, pages = [], "", 0
    lo, hi = close_ts - max(TS) * 60 - 60, close_ts + 120
    while True:
        r = _get(f"/markets/trades?ticker={tk}&min_ts={lo}&max_ts={hi}&limit=1000" + (f"&cursor={cur}" if cur else ""))
        pages += 1
        for t in r.get("trades", []):
            rows.append([iso_us(t["created_time"]), round(float(t["yes_price_dollars"]) * 100, 4),
                         float(t["count_fp"]), t["taker_side"][:1]])
        cur = r.get("cursor")
        if not cur or not r.get("trades"):
            break
    rows.sort()
    return rows, pages


def fetch_event(event, tickers):
    p = os.path.join(TAPE, event + ".json")
    if os.path.exists(p) and jload(p).get("complete"):
        return "cached"
    out = {}
    for tk, ct in tickers:
        rows, pages = fetch_ticker(tk, ct)
        out[tk] = rows
    jdump({"event": event, "complete": True, "fetched_at": int(time.time()), "tape": out}, p)
    return "fetched"


def cmd_tape():
    q = jload(QUOTES)
    by = collections.defaultdict(dict)
    for x in q["quotes"]:
        by[x["event"]][x["ticker"]] = x["close_ts"]
    jobs = [(e, sorted(v.items())) for e, v in by.items()]
    print("events", len(jobs), "tickers", sum(len(v) for _, v in jobs), flush=True)
    t0, n = time.time(), [0]

    def run(j):
        try:
            s = fetch_event(*j)
        except Exception as e:
            print("FAIL", j[0], type(e).__name__, getattr(e, "code", ""), flush=True)
            return "fail"
        n[0] += 1
        if n[0] % 25 == 0:
            print(f"{n[0]}/{len(jobs)} events  {time.time() - t0:.0f}s", flush=True)
        return s

    with ThreadPoolExecutor(5) as ex:
        res = list(ex.map(run, jobs))
    print(collections.Counter(res), flush=True)


# ------------------------------------------------------------------------------------- fills (tape)
def fill_models(rows, t0_us, close_us, a, yes_only=False):
    """rows sorted [(ts_us, price_c, count, side)].  Returns (opt, n25, n100) as fill times in us or None."""
    cum, opt, f25, f100 = 0.0, None, None, None
    for ts, p, c, s in rows:
        if ts <= t0_us:
            continue
        if ts > close_us:
            break
        if p < a - 1e-9 or (yes_only and s != "y"):
            continue
        cum += c
        if opt is None:
            opt = ts
        if f25 is None and cum > 25:
            f25 = ts
        if f100 is None and cum > 100:
            f100 = ts
    return opt, f25, f100


def load_tape(events):
    return {e: jload(os.path.join(TAPE, e + ".json"))["tape"] for e in events}


# ------------------------------------------------------------------------------------- candle-only bracket (anchor f)
def _px(d, key):
    v = d.get(key + "_dollars", d.get(key))
    return None if v is None else float(v) * 100.0


def candle_bracket(raw, t0, close_ts, a):
    """What the CANDLE archive alone can say about volume at price >= a after t0 (cache ends at close-300).
    Rigorous bracket per minute from the trade-price low/high only:  h < a -> (0,0);  l >= a -> (V,V);  else (0,V).
    'mean' bracket additionally assumes price.mean is volume-weighted (validated against the tape in section F1):
        U' = V*(m-l)/(a-l);  L' = V*(m-(a-1))/(h-(a-1)) floored at 0.
    Returns dict with exact optimistic flag and cumulative LB/UB for N=25 in-window."""
    cumL = cumU = cumLm = cumUm = 0.0
    opt = False
    for c in raw or []:
        if c["end_period_ts"] <= t0:
            continue
        V = float(c.get("volume_fp") or 0)
        if V <= 0:
            continue
        pr = c.get("price") or {}
        l, h, m = _px(pr, "low"), _px(pr, "high"), _px(pr, "mean")
        if h is None:
            continue
        if h < a - 1e-9:
            continue
        opt = True
        if l is not None and l >= a - 1e-9:
            cumL += V
            cumU += V
            cumLm += V
            cumUm += V
            continue
        cumU += V
        if m is not None and l is not None and a - l > 0:
            cumUm += min(V, V * max(0.0, m - l) / (a - l))
            if h - (a - 1) > 0:
                cumLm += max(0.0, V * (m - (a - 1)) / (h - (a - 1)))
        else:
            cumUm += V
    return {"opt": opt, "n25_lb": cumL > 25, "n25_ub": cumU > 25, "n25_lb_m": cumLm > 25, "n25_ub_m": cumUm > 25}


# ------------------------------------------------------------------------------------- statistics
from scipy import stats as st
import numpy as np


def cell_stats(rows, model):
    """rows: quotes with fill flags and 'yes' joined.  model: key into row['fill'].  Returns the full cell record."""
    n = len(rows)
    filled = [r for r in rows if r["fill"][model]]
    nf = len(filled)
    kq = sum(r["yes"] for r in rows)
    kf = sum(r["yes"] for r in filled)
    pq, qlo, qhi = wilson(kq, n)
    pf, flo, fhi = wilson(kf, nf) if nf else (None, None, None)
    pnl = [((r["a"] if not r["yes"] else r["a"] - 100.0) if r["fill"][model] else 0.0) for r in rows]
    days = [r["day"] for r in rows]
    cs = TP.cluster_stats(pnl, [1.0] * n, days, fam=FAM) if n else {}
    fdays = {r["day"] for r in filled}
    # per filled
    pnl_f = [((r["a"] if not r["yes"] else r["a"] - 100.0)) for r in filled]
    csf = TP.cluster_stats(pnl_f, [1.0] * nf, [r["day"] for r in filled], fam=FAM) if nf else {}
    mean_a_f = (sum(r["a"] for r in filled) / nf) if nf else None
    mean_a_q = (sum(r["a"] for r in rows) / n) if n else None
    ratio = (pf / pq) if (nf and pq and pq > 0) else (float("inf") if (nf and pf and pf > 0 and pq == 0) else None)
    nonover = bool(nf and flo is not None and flo > qhi)
    # direct standardisation: P(YES|quoted) re-weighted to the filled quotes' price-level mix
    std = None
    if nf:
        byq = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            byq[r["a"]][0] += 1
            byq[r["a"]][1] += r["yes"]
        cntf = collections.Counter(r["a"] for r in filled)
        std = sum(cntf[a] / nf * (byq[a][1] / byq[a][0]) for a in cntf)
    # tail risk
    byday, byhour_exp, byday_f = collections.defaultdict(float), collections.defaultdict(float), collections.defaultdict(float)
    for r, x in zip(rows, pnl):
        byday[r["day"]] += x
    for r in filled:
        byhour_exp[r["event"]] += 100.0 - r["a"]
    worst = min(byday.items(), key=lambda kv: kv[1]) if byday else (None, None)
    wexp = max(byhour_exp.items(), key=lambda kv: kv[1]) if byhour_exp else (None, None)
    # clustered bootstrap (resample days) of P(YES|filled) - P(YES|quoted), in probability points
    boot = None
    if nf:
        dk = sorted({r["day"] for r in rows})
        agg = {d: np.zeros(4) for d in dk}                      # nq, kq, nf, kf
        for r in rows:
            v = agg[r["day"]]
            v[0] += 1
            v[1] += r["yes"]
            if r["fill"][model]:
                v[2] += 1
                v[3] += r["yes"]
        M = np.array([agg[d] for d in dk])
        rng = np.random.default_rng(BOOT_SEED)
        idx = rng.integers(0, len(dk), size=(BOOT_B, len(dk)))
        S = M[idx].sum(axis=1)
        ok = (S[:, 2] > 0) & (S[:, 0] > 0)
        diff = S[ok, 3] / S[ok, 2] - S[ok, 1] / S[ok, 0]
        boot = [float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5)), float(ok.mean())]
    return {
        "n_quoted": n, "k_yes_quoted": kq, "p_yes_quoted": pq, "q_lo": qlo, "q_hi": qhi,
        "n_filled": nf, "k_yes_filled": kf, "p_yes_filled": pf, "f_lo": flo, "f_hi": fhi,
        "fill_rate": nf / n if n else None, "filled_days": len(fdays), "quoted_days": len({r["day"] for r in rows}),
        "ratio": ratio, "nonoverlap_worse": nonover, "p_yes_quoted_std_to_filled_mix": std,
        "mean_a_filled": mean_a_f, "mean_a_quoted": mean_a_q,
        "ev_per_quoted": cs.get("mean"), "se_q": cs.get("se"), "t_q": cs.get("t"), "bar": cs.get("bar"), "G": cs.get("G"),
        "ev_per_filled": csf.get("mean"), "se_f": csf.get("se"), "t_f": csf.get("t"),
        "worst_day": worst[0], "worst_day_pnl_c": worst[1],
        "max_hour_short_exposure_c": wexp[1], "max_hour_exposure_event": wexp[0],
        "boot_diff_ci": boot,
    }


def gates(c):
    """PASS gates 1-5 (spec).  Evaluated for every model but only N=25 is decisive."""
    if not c["n_filled"]:
        return {"g1": False, "g2": False, "g3": False, "g4": False, "g5": False, "pass": False}
    g1 = bool(c["f_hi"] * 100.0 < c["mean_a_filled"])
    g2 = bool(c["ev_per_quoted"] is not None and c["ev_per_quoted"] >= 0.5)
    g3 = bool(c["t_q"] is not None and c["bar"] is not None and c["t_q"] >= c["bar"])
    g4 = bool(c["n_filled"] >= 500 and c["filled_days"] >= 40)
    g5 = bool(c["fill_rate"] >= 0.05)
    return {"g1": g1, "g2": g2, "g3": g3, "g4": g4, "g5": g5, "pass": g1 and g2 and g3 and g4 and g5}


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
        nm = _names(fdefs[f])
        bad = nm & FORBIDDEN_IN_PLACEMENT
        assert not bad, f"anchor (c): {f} references {bad}"
        out["placement_funcs"].append(f)
    # TP.entry_quote itself: no result / no ask (reused verbatim; re-asserted here)
    tp_tree = ast.parse(open(os.path.abspath(TP.__file__)).read())
    tp_f = {n.name: n for n in ast.walk(tp_tree) if isinstance(n, ast.FunctionDef)}
    for f in ("entry_quote", "candle_rows"):
        nm = {x.lower() for x in _names(tp_f[f])}
        assert "result" not in nm and "results" not in nm, f
    out["tp_entry_quote_checked"] = True
    return out


def hand_worked(quotes, tapes, n=10):
    """First n quoted (T=15, k=1) in WORK ORDER.  Re-parses RAW candle JSON independently of TP.entry_quote/normalize."""
    order = jload(os.path.join(TP.CACHE, "work_order.json"))
    pos = {e: i for i, e in enumerate(order)}
    pick = sorted([q for q in quotes if q["T"] == 15 and q["k"] == 1], key=lambda q: (pos[q["event"]], q["ticker"]))[:n]
    rows = []
    for q in pick:
        raw = jload(os.path.join(TP.HOURS, q["event"], "candles.json"))[q["ticker"]]
        cutoff = q["close_ts"] - 15 * 60
        cand = [c for c in raw if c["end_period_ts"] <= cutoff]
        c = max(cand, key=lambda c: c["end_period_ts"])
        b_raw = int(round(float(c["yes_bid"]["close_dollars"]) * 100))
        assert b_raw == q["b"] and b_raw + 1 == q["a"], (q["ticker"], b_raw, q["b"])
        assert c["end_period_ts"] <= cutoff
        later = [x["end_period_ts"] for x in raw if x["end_period_ts"] > cutoff]
        opt, f25, f100 = fill_models(tapes[q["event"]][q["ticker"]], cutoff * 1_000_000, q["close_ts"] * 1_000_000, q["a"])
        rows.append({"ticker": q["ticker"], "cutoff_ts": cutoff, "entry_candle_end_ts": c["end_period_ts"],
                     "raw_yes_bid_close": c["yes_bid"]["close_dollars"], "b": b_raw, "a": q["a"],
                     "first_candle_after_cutoff": (min(later) if later else None),
                     "fill_opt": opt is not None, "fill_n25": f25 is not None, "fill_n100": f100 is not None})
    return rows


# ------------------------------------------------------------------------------------- analyze
def cmd_analyze():
    chk = anchor_static_checks()
    global OUT_JSON, OUT_MD
    qd = jload(QUOTES)
    quotes, hours = qd["quotes"], qd["hours"]
    dry = bool(os.environ.get("MF_DRY"))                    # code-path smoke test on a partial tape; writes to scratch, no sha check
    if dry:
        hours = [h for h in hours if os.path.exists(os.path.join(TAPE, h + ".json"))]
        hs = set(hours)
        quotes = [q for q in quotes if q["event"] in hs]
        OUT_JSON, OUT_MD = os.environ["MF_DRY"] + ".json", os.environ["MF_DRY"] + ".md"
    else:
        # anchor c: the saved placement must equal a fresh recomputation (no drift, no later edit)
        fresh = []
        for e in hours:
            fresh += place_hour(e)[0]
        assert hashlib.sha256(json.dumps(fresh, sort_keys=True).encode()).hexdigest() == qd["sha256"], "placement drifted"
    assert all(q["stale"] >= 0 for q in quotes)
    hours_all = jload(os.path.join(TP.CACHE, "hours_universe.json"))
    tapes = load_tape(hours)                                # first moment the tape is read
    hand = hand_worked(quotes, tapes)

    # ---- fills (tape) -- still no outcome loaded
    cand_cache = {}
    for q in quotes:
        t0 = (q["close_ts"] - q["T"] * 60) * 1_000_000
        cl = q["close_ts"] * 1_000_000
        rows = tapes[q["event"]][q["ticker"]]
        o, f25, f100 = fill_models(rows, t0, cl, q["a"])
        yo, y25, y100 = fill_models(rows, t0, cl, q["a"], yes_only=True)
        q["fill"] = {"opt": o is not None, "n25": f25 is not None, "n100": f100 is not None}
        q["fill_yes_only"] = {"opt": yo is not None, "n25": y25 is not None, "n100": y100 is not None}
        q["t_fill_opt"], q["t_fill_n25"] = o, f25
        q["fill_in_cache_window"] = (o is not None and o <= (q["close_ts"] - 300) * 1_000_000)
        q["fill_last5"] = (o is not None and o > (q["close_ts"] - 300) * 1_000_000)

    # ---- section F1: candle-only bracket vs tape (no outcome)
    f1 = candle_section(quotes, tapes, hours)

    # ---- outcomes: first loaded here
    results = TP.load_results_for(hours)
    excl = collections.Counter()
    rows = []
    for q in quotes:
        r = results[q["event"]].get(q["ticker"])
        if r not in ("yes", "no"):
            excl["no_official_yes_no_result"] += 1
            continue
        q["yes"] = 1 if r == "yes" else 0
        rows.append(q)

    cells = {}
    for T in TS:
        for k in KS:
            sub = [r for r in rows if r["T"] == T and r["k"] == k]
            for m in MODELS:
                c = cell_stats(sub, m)
                c["gates"] = gates(c)
                cells[f"{T}|{k}|{m}"] = c
            # sensitivity: taker-yes-only prints
            sub2 = [{**r, "fill": r["fill_yes_only"]} for r in sub]
            for m in MODELS:
                c = cell_stats(sub2, m)
                cells[f"{T}|{k}|{m}|yesonly"] = c
    # price-level stratification, T=15, k pooled
    levels = [("2", 2, 2), ("3", 3, 3), ("4-5", 4, 5), ("6-10", 6, 10), ("11-20", 11, 20)]
    bylevel = {}
    for T in TS:
        for name, lo, hi in levels:
            sub = [r for r in rows if r["T"] == T and lo <= r["a"] <= hi]
            for m in ("opt", "n25"):
                bylevel[f"{T}|{name}|{m}"] = cell_stats(sub, m)
    # staleness diagnostic (single pre-declared split at 120 s), N=25
    stale_split = {}
    for T in TS:
        for k in (1, 2):
            for nm, f in (("fresh<=120s", lambda r: r["stale"] <= 120), ("stale>120s", lambda r: r["stale"] > 120)):
                sub = [r for r in rows if r["T"] == T and r["k"] == k and f(r)]
                for m in ("opt", "n25"):
                    stale_split[f"{T}|{k}|{nm}|{m}"] = cell_stats(sub, m)

    # verdict (N=25 decisive)
    dec = {key: c for key, c in cells.items() if key.endswith("|n25")}
    passing = [key for key, c in dec.items() if c["gates"]["pass"]]
    floor = [key for key, c in dec.items() if c["gates"]["g4"]]
    killc = {key: bool(cells[key]["ratio"] is not None and cells[key]["ratio"] >= 2 and cells[key]["nonoverlap_worse"]) for key in floor}
    kill = bool(floor) and all(killc.values())
    verdict = "PASS" if passing else ("KILL" if kill else "INSUFFICIENT")
    # sensitivity verdicts (disclosure, not decisive)
    sens = {}
    for m in ("opt", "n100"):
        d = {key: c for key, c in cells.items() if key.endswith("|" + m)}
        p = [key for key, c in d.items() if c["gates"]["pass"]]
        fl = [key for key, c in d.items() if c["gates"]["g4"]]
        kl = {key: bool(c["ratio"] is not None and c["ratio"] >= 2 and c["nonoverlap_worse"]) for key, c in d.items() if key in fl}
        sens[m] = {"pass": p, "floor": fl, "kill_cells": kl,
                   "verdict": "PASS" if p else ("KILL" if (fl and all(kl.values())) else "INSUFFICIENT")}

    # exposure scale
    rep = {
        "spec": "MAKER_FILL_SPEC.md", "verdict": verdict,
        "sampling": {"hours_priced": len(hours), "hours_universe": len(hours_all),
                     "days": len({q["day"] for q in quotes}), "quotes": len(quotes), "quotes_with_result": len(rows),
                     "quotes_sha256": qd["sha256"]},
        "exclusions": {"placement": qd["excl"], "result": dict(excl)},
        "cells": cells, "bylevel": bylevel, "stale_split": stale_split,
        "pass_cells": passing, "floor_cells_n25": floor, "kill_cells_n25": killc, "sensitivity": sens,
        "f1": f1, "anchors": {"static": chk, "hand_worked": hand},
        "bonferroni": {"family": FAM, "alpha_two_sided": 0.05 / FAM, "p": 1 - 0.05 / FAM / 2},
    }
    jdump(rep, OUT_JSON)
    write_md(rep, OUT_MD)
    print("verdict", verdict, "quotes", len(quotes), "with result", len(rows))
    return rep


def candle_section(quotes, tapes, hours):
    """Anchor (f) evidence.  (1) tape vs candle volume integrity per minute; (2) VWAP check of price.mean;
    (3) bracket width of candle-only fill attribution; (4) share of fills the cache window cannot see."""
    vol_match = tot_min = 0
    vsum_c = vsum_t = 0.0
    mean_vw_ok = mean_sm_ok = mean_n = 0
    for e in hours[:120]:                                   # integrity sample: first 120 hours in work order
        cdl = jload(os.path.join(TP.HOURS, e, "candles.json"))
        close_e = jload(os.path.join(TP.HOURS, e, "ladder.json"))[0]["close_ts"]
        tape_lo = close_e - max(TS) * 60 - 60            # the tape window starts here; earlier candle minutes are not comparable
        for tk, rows in tapes[e].items():
            raw = cdl.get(tk) or []
            bymin = collections.defaultdict(list)
            for ts, p, c, s in rows:
                bymin[(ts + 60_000_000 - 1) // 60_000_000 * 60].append((p, c))
            for cd in raw:
                V = float(cd.get("volume_fp") or 0)
                end = cd["end_period_ts"]
                if V <= 0 or end - 60 < tape_lo:
                    continue
                trs = bymin.get(end, [])
                tv = sum(c for _, c in trs)
                tot_min += 1
                vsum_c += V
                vsum_t += tv
                vol_match += abs(tv - V) < 0.015
                pr = cd.get("price") or {}
                m = _px(pr, "mean")
                if m is not None and trs and abs(tv - V) < 0.015:
                    vw = sum(p * c for p, c in trs) / tv
                    sm = sum(p for p, _ in trs) / len(trs)
                    mean_n += 1
                    mean_vw_ok += abs(vw - m) < 0.51
                    mean_sm_ok += abs(sm - m) < 0.51
    # bracket width on in-window candle data
    br = collections.Counter()
    cache = {}
    for q in quotes:
        if q["T"] == 5:
            br[(q["T"], q["k"], "no_post_T_candle_in_cache")] += 1
            continue
        key = q["event"]
        if key not in cache:
            cache = {key: jload(os.path.join(TP.HOURS, key, "candles.json"))}
        raw = cache[key].get(q["ticker"])
        t0 = q["close_ts"] - q["T"] * 60
        b = candle_bracket(raw, t0, q["close_ts"], q["a"])
        tp = tapes[q["event"]][q["ticker"]]
        o, f25, f100 = fill_models(tp, t0 * 1_000_000, (q["close_ts"] - 300) * 1_000_000, q["a"])   # tape clipped to cache window
        cell = (q["T"], q["k"])
        br[cell + ("n",)] += 1
        br[cell + ("amb_rigorous",)] += (b["n25_lb"] != b["n25_ub"])
        br[cell + ("amb_mean",)] += (b["n25_lb_m"] != b["n25_ub_m"])
        br[cell + ("tape_in_rigorous",)] += (b["n25_lb"] <= (f25 is not None) <= b["n25_ub"])
        br[cell + ("tape_in_mean",)] += (b["n25_lb_m"] <= (f25 is not None) <= b["n25_ub_m"])
        br[cell + ("opt_candle_eq_tape",)] += (b["opt"] == (o is not None))
        br[cell + ("lb_fill",)] += b["n25_lb"]
        br[cell + ("ub_fill",)] += b["n25_ub"]
        br[cell + ("tape_fill_in_window",)] += (f25 is not None)
    last5 = collections.Counter()
    gaps = []
    for e in hours:
        cd = jload(os.path.join(TP.HOURS, e, "candles.json"))
        lad = jload(os.path.join(TP.HOURS, e, "ladder.json"))
        for m in lad:
            v = cd.get(m["ticker"])
            if v:
                gaps.append(m["close_ts"] - max(x["end_period_ts"] for x in v))
    min_gap = min(gaps)
    after_close = total_prints = 0
    for e in hours:
        close_e = jload(os.path.join(TP.HOURS, e, "ladder.json"))[0]["close_ts"] * 1_000_000
        for rws in tapes[e].values():
            total_prints += len(rws)
            after_close += sum(1 for r in rws if r[0] > close_e)
    for q in quotes:
        c = (q["T"], q["k"])
        last5[c + ("opt_total",)] += q["fill"]["opt"]
        last5[c + ("opt_first_fill_in_last5",)] += q["fill_last5"]
        last5[c + ("n25_total",)] += q["fill"]["n25"]
        last5[c + ("n25_fill_time_in_last5",)] += (q["t_fill_n25"] is not None and q["t_fill_n25"] > (q["close_ts"] - 300) * 1_000_000)
    return {"min_gap_s": min_gap, "prints_total": total_prints, "prints_after_close": after_close, "n_strikes_with_candles": len(gaps), "minute_vol_compare": {"minutes": tot_min, "exact_match": vol_match, "candle_vol": vsum_c, "tape_vol": vsum_t},
            "mean_check": {"n": mean_n, "vwap_within_0p5c": mean_vw_ok, "simple_mean_within_0p5c": mean_sm_ok},
            "bracket": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in br.items()},
            "last5": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in last5.items()}}


# ------------------------------------------------------------------------------------- report
PLAIN_READING: list = []          # filled in AFTER the run, from the tables below (post-hoc prose, no bar depends on it)


def _f(x, nd=2, pct=False):
    if x is None:
        return "n/a"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return f"{x * 100:.{nd}f}%" if pct else f"{x:.{nd}f}"


def _ci(lo, hi):
    return "n/a" if lo is None else f"[{lo * 100:.2f}%, {hi * 100:.2f}%]"


def write_md(rep, path):
    C, L = rep["cells"], []
    S, F1 = rep["sampling"], rep["f1"]
    L.append("# Maker fill: does a fee-free resting ask on KXBTCD longshots survive adverse selection?  (MAKER_FILL_SPEC.md, executed)\n")
    L.append(f"**VERDICT: {rep['verdict']}**  (frozen PASS/KILL rule applied verbatim, N=25 decisive; numbers beside each bar in section 6)\n")
    L.append(f"Sample: {S['hours_priced']} of {S['hours_universe']} hourly events, {S['days']} UTC days, {S['quotes']:,} quotes "
             f"(placement sha256 `{S['quotes_sha256'][:16]}`), {S['quotes_with_result']:,} with an official yes/no result.\n")
    if PLAIN_READING:
        L.append("## 0. Plain reading (written after the run; numbers are from the tables below)\n")
        L += ["* " + x for x in PLAIN_READING]
        L.append("")
    # ---------------------------------------------------------------- F
    L.append("## 1. Anchor (f): volume provenance -- resolution FIRST\n")
    for x in F1_TEXT:
        L.append(x)
    mv, mc = F1["minute_vol_compare"], F1["mean_check"]
    L.append("\n**F-i. The tape reproduces the candle archive** (integrity of the replacement data). First 120 hours in work order, every candle minute with volume > 0, tape prints re-bucketed into (end-60s, end]:\n")
    L.append(f"* minutes compared: {mv['minutes']:,}; exact per-minute volume match (|diff| < 0.015 contracts): {mv['exact_match']:,} ({mv['exact_match'] / max(1, mv['minutes']) * 100:.2f}%); "
             f"total candle volume {mv['candle_vol']:,.1f} vs total tape volume {mv['tape_vol']:,.1f} (ratio {mv['tape_vol'] / max(1e-9, mv['candle_vol']):.4f}).")
    L.append(f"* `price.mean_dollars` check on exactly-matching minutes (n={mc['n']:,}): volume-weighted tape mean within 0.5c of the candle mean in {mc['vwap_within_0p5c']:,} ({mc['vwap_within_0p5c'] / max(1, mc['n']) * 100:.1f}%); "
             f"simple (unweighted) mean within 0.5c in {mc['simple_mean_within_0p5c']:,} ({mc['simple_mean_within_0p5c'] / max(1, mc['n']) * 100:.1f}%). "
             "The mean-tightened bracket below therefore rests on a validated, not assumed, definition.")
    L.append("\n**F-ii. What the candles alone can and cannot say (N=25 pessimistic, in-window only, T=5 excluded because no post-T candle exists).** "
             "`rigorous` = bracket from trade-price low/high only; `mean-tight` = also uses the volume-weighted mean. A quote is *ambiguous* when the lower-bound and upper-bound fill status disagree. "
             "`tape in bracket` checks the bracket logic against the tape clipped to the same window (must be 100%).\n")
    L.append("| T | k | quotes | LB fills | UB fills | tape fills (in window) | ambiguous (rigorous) | ambiguous (mean-tight) | tape inside rigorous | tape inside mean-tight | candle-optimistic == tape-optimistic |")
    L.append("|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    br = F1["bracket"]
    for T in TS:
        for k in KS:
            if T == 5:
                L.append(f"| 5 | {k} | {br.get(f'5|{k}|no_post_T_candle_in_cache', 0):,} | no candle after T exists in the cache | | | | | | | |")
                continue
            n = br.get(f"{T}|{k}|n", 0)
            g = lambda s: br.get(f"{T}|{k}|{s}", 0)
            L.append(f"| {T} | {k} | {n:,} | {g('lb_fill'):,} | {g('ub_fill'):,} | {g('tape_fill_in_window'):,} | {g('amb_rigorous') / max(1, n) * 100:.1f}% | "
                     f"{g('amb_mean') / max(1, n) * 100:.1f}% | {g('tape_in_rigorous') / max(1, n) * 100:.1f}% | {g('tape_in_mean') / max(1, n) * 100:.1f}% | {g('opt_candle_eq_tape') / max(1, n) * 100:.1f}% |")
    L.append("\n**F-iii. What the candle cache cannot see: the last 5 minutes before close** (the original fetch stopped at close-300s; min over all strikes of close - last candle end = "
             f"{F1.get('min_gap_s')}s). Share of FILLED quotes (tape, optimistic) whose first fill is inside the final 5 minutes, and share of N=25 fills completing there:\n")
    L.append("| T | k | optimistic fills | first fill in final 5 min | N=25 fills | N=25 fill completes in final 5 min |")
    L.append("|--:|--:|--:|--:|--:|--:|")
    l5 = F1["last5"]
    for T in TS:
        for k in KS:
            g = lambda s: l5.get(f"{T}|{k}|{s}", 0)
            L.append(f"| {T} | {k} | {g('opt_total'):,} | {g('opt_first_fill_in_last5'):,} ({g('opt_first_fill_in_last5') / max(1, g('opt_total')) * 100:.1f}%) | "
                     f"{g('n25_total'):,} | {g('n25_fill_time_in_last5'):,} ({g('n25_fill_time_in_last5') / max(1, g('n25_total')) * 100:.1f}%) |")
    # ---------------------------------------------------------------- A
    L.append("\n## 2. Anchor (a): adverse selection -- P(YES | filled) vs P(YES | quoted), per cell, BEFORE any EV\n")
    L.append("Same cell = same (k, T) quote rule; `quoted` is every quote placed in the cell (unfilled included), `filled` the subset the model fills. "
             "Wilson 95% intervals treat strikes as independent, which they are not (one BTC move hits every strike of an hour); the `day-bootstrap` column resamples whole UTC days "
             f"({BOOT_B} draws, seed {BOOT_SEED}) for the difference P(YES|filled) - P(YES|quoted) in percentage points and is the honest width. "
             "`std. quoted` = P(YES|quoted) re-weighted to the price-level mix of the filled quotes (removes the composition effect that a mixed-price cell can create). "
             "`break-even` = mean ask of the filled quotes /100: the YES rate at which a fee-free short is exactly flat. KILL column: ratio >= 2 AND Wilson(filled).lo > Wilson(quoted).hi.\n")
    for m in MODELS:
        L.append(f"\n### {MODEL_LABEL[m]}{'  (DECISIVE for the verdict)' if m == 'n25' else ''}\n")
        L.append("| T | k | quoted n | P(YES|quoted) [Wilson] | filled n | P(YES|filled) [Wilson] | ratio | std. quoted | break-even | day-bootstrap 95% of diff (pp) | KILL cond. |")
        L.append("|--:|--:|--:|---|--:|---|--:|--:|--:|---|:--:|")
        for T in TS:
            for k in KS:
                c = C[f"{T}|{k}|{m}"]
                bd = c["boot_diff_ci"]
                bs = "n/a" if not bd else f"[{bd[0] * 100:+.2f}, {bd[1] * 100:+.2f}]"
                kc = "n/a" if not c["n_filled"] else ("YES" if (c["ratio"] is not None and c["ratio"] >= 2 and c["nonoverlap_worse"]) else "no")
                L.append(f"| {T} | {k} | {c['n_quoted']:,} | {_f(c['p_yes_quoted'], 2, True)} {_ci(c['q_lo'], c['q_hi'])} | {c['n_filled']:,} | "
                         f"{_f(c['p_yes_filled'], 2, True)} {_ci(c['f_lo'], c['f_hi'])} | {_f(c['ratio'], 2)} | {_f(c['p_yes_quoted_std_to_filled_mix'], 2, True)} | "
                         f"{_f(None if c['mean_a_filled'] is None else c['mean_a_filled'] / 100, 2, True)} | {bs} | {kc} |")
    L.append("\n### Same price level (pooled over k; ask level a), optimistic and N=25\n")
    L.append("| T | ask a | model | quoted n | P(YES|quoted) [Wilson] | filled n | P(YES|filled) [Wilson] | ratio | break-even |")
    L.append("|--:|---|---|--:|---|--:|---|--:|--:|")
    for T in TS:
        for name in ("2", "3", "4-5", "6-10", "11-20"):
            for m in ("opt", "n25"):
                c = rep["bylevel"][f"{T}|{name}|{m}"]
                if not c["n_quoted"]:
                    continue
                L.append(f"| {T} | {name}c | {m} | {c['n_quoted']:,} | {_f(c['p_yes_quoted'], 2, True)} {_ci(c['q_lo'], c['q_hi'])} | {c['n_filled']:,} | "
                         f"{_f(c['p_yes_filled'], 2, True)} {_ci(c['f_lo'], c['f_hi'])} | {_f(c['ratio'], 2)} | {_f(None if c['mean_a_filled'] is None else c['mean_a_filled'] / 100, 2, True)} |")
    L.append("\n### Sensitivity: only prints with taker_side = yes count toward the fill (prints that actually lifted offers); N=25 and optimistic\n")
    L.append("| T | k | model | filled n | P(YES|filled) [Wilson] | P(YES|quoted) | ratio |")
    L.append("|--:|--:|---|--:|---|--:|--:|")
    for T in TS:
        for k in KS:
            for m in ("opt", "n25"):
                c = C[f"{T}|{k}|{m}|yesonly"]
                L.append(f"| {T} | {k} | {m} | {c['n_filled']:,} | {_f(c['p_yes_filled'], 2, True)} {_ci(c['f_lo'], c['f_hi'])} | {_f(c['p_yes_quoted'], 2, True)} | {_f(c['ratio'], 2)} |")
    L.append("\n### Diagnostic (single pre-declared split, not a filter): entry-candle age <= 120 s vs > 120 s, k = 1, 2\n")
    L.append("| T | k | candle age | model | quoted n | P(YES|quoted) | filled n | P(YES|filled) [Wilson] |")
    L.append("|--:|--:|---|---|--:|--:|--:|---|")
    for T in TS:
        for k in (1, 2):
            for nm in ("fresh<=120s", "stale>120s"):
                for m in ("opt", "n25"):
                    c = rep["stale_split"][f"{T}|{k}|{nm}|{m}"]
                    L.append(f"| {T} | {k} | {nm} | {m} | {c['n_quoted']:,} | {_f(c['p_yes_quoted'], 2, True)} | {c['n_filled']:,} | {_f(c['p_yes_filled'], 2, True)} {_ci(c['f_lo'], c['f_hi'])} |")
    # ---------------------------------------------------------------- B
    L.append("\n## 3. Anchor (b): quote counts, fill counts, fill rates -- unfilled quotes are in every denominator\n")
    L.append("| T | k | quotes | days | opt fills | opt rate | N=25 fills | N=25 rate | N=25 filled days | N=100 fills | N=100 rate | N=100 filled days |")
    L.append("|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for T in TS:
        for k in KS:
            o, a, b = C[f"{T}|{k}|opt"], C[f"{T}|{k}|n25"], C[f"{T}|{k}|n100"]
            L.append(f"| {T} | {k} | {o['n_quoted']:,} | {o['quoted_days']} | {o['n_filled']:,} | {_f(o['fill_rate'], 1, True)} | {a['n_filled']:,} | {_f(a['fill_rate'], 1, True)} | {a['filled_days']} | "
                     f"{b['n_filled']:,} | {_f(b['fill_rate'], 1, True)} | {b['filled_days']} |")
    # ---------------------------------------------------------------- EV
    L.append("\n## 4. EV (fee-free, cents), per QUOTED contract beside per FILLED contract\n")
    L.append(f"Per-quoted EV = sum of P&L over filled quotes / all quotes (unfilled = 0). Signed t is day-clustered (CR1, equal weight, df = days - 1) on the per-quoted series. "
             f"Bonferroni: {FAM} comparisons, two-sided alpha = {rep['bonferroni']['alpha_two_sided']:.5f}, bar = Student-t quantile at p = {rep['bonferroni']['p']:.5f}. "
             "Per-filled EV = mean(a) - 100 x P(YES|filled) exactly.\n")
    for m in MODELS:
        L.append(f"\n### {MODEL_LABEL[m]}\n")
        L.append("| T | k | quotes | filled | EV per quoted | SE | t (signed) | bar | EV per filled | t (per filled) | mean ask filled | gates 1/2/3/4/5 | all five |")
        L.append("|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|:--:|")
        for T in TS:
            for k in KS:
                c = C[f"{T}|{k}|{m}"]
                g = c["gates"]
                gs = "/".join("Y" if g[x] else "n" for x in ("g1", "g2", "g3", "g4", "g5"))
                L.append(f"| {T} | {k} | {c['n_quoted']:,} | {c['n_filled']:,} | {_f(c['ev_per_quoted'], 3)} | {_f(c['se_q'], 3)} | {_f(c['t_q'], 2)} | {_f(c['bar'], 2)} | "
                         f"{_f(c['ev_per_filled'], 2)} | {_f(c['t_f'], 2)} | {_f(c['mean_a_filled'], 2)} | {gs} | {'PASS' if g['pass'] else 'no'} |")
    # ---------------------------------------------------------------- c d e
    L.append("\n## 5. Anchors (c), (d), (e)\n")
    a = rep["anchors"]
    L.append(f"**(c) No look-ahead in placement.** AST scan passed: placement functions {a['static']['placement_funcs']} reference none of the forbidden names "
             f"({', '.join(sorted(FORBIDDEN_IN_PLACEMENT))}); `tail_pricing.entry_quote`/`candle_rows` reference no result. "
             "Placement is a separate pass (`quotes`) that writes `quotes.json` before the tape or any result is read; `analyze` recomputes placement from the candle cache and asserts the sha256 equals the saved one, "
             "and asserts every quote's entry-candle age is >= 0 (candle end <= cutoff). The quote price is the entry candle's `yes_bid.close` + k; nothing after the cutoff enters it. "
             "Ten hand-worked placements (T=15, k=1, first ten in work order), raw candle JSON re-parsed independently of `normalize()`; the fill columns are the tape result AFTER placement:\n")
    L.append("| ticker | cutoff ts | entry candle end (<= cutoff) | raw yes_bid close | b | a = b+1 | first candle after cutoff | opt fill | N=25 | N=100 |")
    L.append("|---|--:|--:|--:|--:|--:|--:|:--:|:--:|:--:|")
    for h in a["hand_worked"]:
        L.append(f"| {h['ticker']} | {h['cutoff_ts']} | {h['entry_candle_end_ts']} | {h['raw_yes_bid_close']} | {h['b']} | {h['a']} | {h['first_candle_after_cutoff']} | "
                 f"{'Y' if h['fill_opt'] else 'n'} | {'Y' if h['fill_n25'] else 'n'} | {'Y' if h['fill_n100'] else 'n'} |")
    L.append("\n**(d) Queue assumption.** Book depth is NOT in any archive available here (candles or trade tape): the number of contracts resting ahead of a quote at its price is unobserved. "
             "`N` is therefore an explicit assumption (25 = the deployed `DEPTH_CAP`, 100 = a deeper queue), and the optimistic bound assumes front of queue (N=0), which this program has already shown is optimistic. "
             "How the answer moves with N:\n")
    L.append("| fill model | cells with n_filled>=500 & >=40 filled days | cells passing all five gates | verdict if struck on this model |")
    L.append("|---|--:|--:|---|")
    L.append(f"| optimistic | {len(rep['sensitivity']['opt']['floor'])} | {len(rep['sensitivity']['opt']['pass'])} | {rep['sensitivity']['opt']['verdict']} |")
    L.append(f"| N=25 (decisive) | {len(rep['floor_cells_n25'])} | {len(rep['pass_cells'])} | {rep['verdict']} |")
    L.append(f"| N=100 | {len(rep['sensitivity']['n100']['floor'])} | {len(rep['sensitivity']['n100']['pass'])} | {rep['sensitivity']['n100']['verdict']} |")
    L.append("\n**(e) Tail risk** (SAMPLED hours only: a full-universe day holds about "
             f"{S['hours_universe'] / S['hours_priced']:.1f}x as many positions, so absolute losses are understated by roughly that factor). Worst single UTC day aggregate P&L over the cell's filled quotes; "
             "maximum simultaneous short exposure = largest single-hour sum of (100 - a) over filled quotes (all positions of one hour are open together; hours do not overlap), cents, 100c = $1.\n")
    L.append("| T | k | model | filled | worst day (UTC) | worst-day P&L (c) | max hour short exposure (c) |")
    L.append("|--:|--:|---|--:|---|--:|--:|")
    for T in TS:
        for k in KS:
            for m in ("opt", "n25"):
                c = C[f"{T}|{k}|{m}"]
                L.append(f"| {T} | {k} | {m} | {c['n_filled']:,} | {c['worst_day']} | {_f(c['worst_day_pnl_c'], 0)} | {_f(c['max_hour_short_exposure_c'], 0)} |")
    # ---------------------------------------------------------------- verdict
    L.append("\n## 6. Verdict: frozen rule, numbers beside each bar (N=25 decisive)\n")
    K = {k: C[k] for k in C if k.endswith("|n25")}
    L.append(f"* Cells meeting the n floor (n_filled >= 500 AND >= 40 filled days) under N=25: **{len(rep['floor_cells_n25'])} of 12** ({', '.join(rep['floor_cells_n25']) or 'none'}).")
    L.append(f"* PASS cells (all five gates): **{len(rep['pass_cells'])}** ({', '.join(rep['pass_cells']) or 'none'}).")
    best = max((c for c in K.values() if c["n_filled"]), key=lambda c: (c["ev_per_quoted"] if c["ev_per_quoted"] is not None else -1e9), default=None)
    if best:
        key = [k for k, v in K.items() if v is best][0]
        g = best["gates"]
        L.append(f"* Best cell by EV per quoted under N=25: **{key}** -- quotes {best['n_quoted']:,}, filled {best['n_filled']:,} over {best['filled_days']} days:")
        L.append(f"  * Gate 1 (Wilson UB of P(YES|filled) < mean ask/100): UB {_f(best['f_hi'], 2, True)} vs {_f(best['mean_a_filled'] / 100, 2, True)} -> {'met' if g['g1'] else 'NOT met'}.")
        L.append(f"  * Gate 2 (EV per quoted >= +0.5c): {_f(best['ev_per_quoted'], 3)}c -> {'met' if g['g2'] else 'NOT met'}.")
        L.append(f"  * Gate 3 (signed day-clustered t >= bar): t = {_f(best['t_q'], 2)} vs bar {_f(best['bar'], 2)} -> {'met' if g['g3'] else 'NOT met'}.")
        L.append(f"  * Gate 4 (n_filled >= 500 over >= 40 days): {best['n_filled']:,} over {best['filled_days']} -> {'met' if g['g4'] else 'NOT met'}.")
        L.append(f"  * Gate 5 (fill rate >= 5%): {_f(best['fill_rate'], 1, True)} -> {'met' if g['g5'] else 'NOT met'}.")
    L.append("\nKILL clause (every floor-meeting cell must show P(YES|filled) >= 2 x P(YES|quoted) with non-overlapping Wilson 95%):\n")
    L.append("| cell | filled n | P(YES|quoted) [Wilson] | P(YES|filled) [Wilson] | ratio (bar 2.0) | non-overlap | fires |")
    L.append("|---|--:|---|---|--:|:--:|:--:|")
    for key in rep["floor_cells_n25"]:
        c = C[key]
        L.append(f"| {key} | {c['n_filled']:,} | {_f(c['p_yes_quoted'], 2, True)} {_ci(c['q_lo'], c['q_hi'])} | {_f(c['p_yes_filled'], 2, True)} {_ci(c['f_lo'], c['f_hi'])} | "
                 f"{_f(c['ratio'], 2)} | {'yes' if c['nonoverlap_worse'] else 'no'} | {'YES' if rep['kill_cells_n25'][key] else 'no'} |")
    if not rep["floor_cells_n25"]:
        L.append("| (no cell meets the n floor: the KILL clause cannot fire) | | | | | | |")
    # ---------------------------------------------------------------- exclusions
    L.append("\n## 7. Exclusions (count and reason)\n")
    ex = rep["exclusions"]["placement"]
    L.append("| T | untradeable (no candle / yes_bid = 0), strike-T obs | no candle | quote skipped: a = bid+k > 20c (k=1 / k=2 / k=3) |")
    L.append("|--:|--:|--:|---|")
    for T in TS:
        z = ex.get(str((T, 1, "bid_zero")), 0)
        nc = ex.get(str((T, 1, "no_candle")), 0)
        L.append(f"| {T} | {z + nc:,} | {nc:,} | {ex.get(str((T, 1, 'a_gt_cap')), 0):,} / {ex.get(str((T, 2, 'a_gt_cap')), 0):,} / {ex.get(str((T, 3, 'a_gt_cap')), 0):,} |")
    L.append(f"\n* Untradeable strike-T observations are never quoted (a = yes_bid + k is undefined at bid 0) and are not in any denominator below; they are 41,748-44,026 of 92,560 per T, as in the tail-pricing study.")
    L.append(f"* Non -T / non-greater strikes: {ex.get('non_T_or_non_greater_strike', 0)}.  Quotes without an official yes/no `result`: {rep['exclusions']['result'].get('no_official_yes_no_result', 0)}.")
    L.append("* Quotes with a > 20c are outside the frozen placed universe (cap); the spec line 'above 20c is reported but cannot PASS' is read as a statement about that excluded region, not as an instruction to simulate it. Counts above.")
    L.append("* Calendar day = UTC date of close. Universe: the 503 completed hours of the tail-pricing cache (prefix of the saved seed-20261027 shuffle; never re-sorted); no hour added.")
    L.append("* Interpretation choices fixed before any fill or outcome was computed are listed in the docstring of `maker_fill.py`.")
    open(path, "w").write("\n".join(L) + "\n")


F1_TEXT = [
    "**Resolution.** *Candle archive alone: NOT-MEASURABLE* for the pessimistic fill models (and for T=5 and the final five minutes of every cell). "
    "*Hugging Face `TrevorJS/kalshi-trades`: does not cover this window* (its card states trades run June 2021 - January 2026, last modified 2026-01-30; the universe is closes 2026-08-22..2026-10-20). "
    "*The public Kalshi API `GET /markets/trades` does carry the missing data* -- every print with `yes_price`, `count_fp`, `taker_side` and a microsecond `created_time` -- for exactly this window, "
    "so price-conditional volume is MEASURED from prints rather than attributed. The study below runs on that tape, fetched into `cache/maker_fill/tape/` for the 3,371 strikes the frozen placement rule quotes; no hour was added.\n",
    "Why the candles cannot do it: a candle row carries total `volume_fp` plus only the trade-price low/high/open/close/mean of the minute. "
    "(1) If `high < a` the minute had no volume at >= a, and if `low >= a` all of it did -- both are identified. If `low < a <= high` -- the normal case for a quote one to three cents above the bid in a minute that traded on both sides -- "
    "volume at >= a can be anything from ~0 to the full minute, so the cumulative-volume-exceeds-N rule is undetermined. The volume-weighted mean narrows it but does not close it (F-ii). "
    "(2) Independently of that, the cache holds no candle after close-300s, so 'held to close' cannot be observed for any cell and T=5 has no post-quote data at all (F-iii).\n",
]


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    {"quotes": cmd_quotes, "tape": cmd_tape, "analyze": cmd_analyze}[c]()
