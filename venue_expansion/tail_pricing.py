"""tail_pricing.py -- executes TAIL_PRICING_SPEC.md (registered 2026-10-27).  Nothing here may move a bar.

QUESTION. Are Kalshi KXBTCD (BTC hourly, threshold -T strikes) longshot YES prices higher than the
frequencies they realise, by enough to survive the executable spread and the taker fee?  Strategy under
test: SELL YES at the candle's yes_bid.  Risk-premium test; no information used.

HARD RULES IMPLEMENTED (and asserted at run time by `anchor_static_checks`):
  (a) Sale price is yes_bid.  `100 - yes_ask` is computed NOWHERE (AST scan of this whole module).
      yes_ask is not even unpacked in the pricing/P&L path.
  (b) The official `result` field is NOT read by the fetch->ladder->pricing path.  The listing is split on
      disk into ladder.json (no result) and results.json; only `pnl_step()` and the integrity checks
      load results.json.  AST + source scan asserts it.
  Entry: last candle with end_period_ts <= close - T*60, T in {5,15,30,45}.  No search over minutes.
  A strike-T with no such candle, or yes_bid == 0 / missing, is UNTRADEABLE: stays in the denominator,
  never priced, never back-filled.
  Sampling: whole HOURS (event tickers) in a seeded shuffle (seed 20261027) saved to work_order.json and
  NEVER re-sorted.  Analysis uses the completed hours; because work is done strictly in shuffled order the
  completed set is a prefix of a random permutation, i.e. itself a uniform random sample of hours.

INTERPRETATION CHOICES FIXED BEFORE ANY OUTCOME WAS READ (spec silent):
  * Calendar day = UTC date of close_time (cluster unit).  Hour-clustered view is robustness only.
  * Universe window: hourly events with strike_date in [2026-08-22T00:00Z, 2026-10-21T00:00Z): 60 UTC days
    (closes through 2026-10-20 inclusive).
  * Volume-weighted reading: weight = volume_fp of the ENTRY candle (contracts traded in that minute).
  * "Untradeable fraction in the cell" (gate 4): PRIMARY = the entry-time-level fraction
        U_T = (strike-T with no candle or yes_bid==0) / (all strike-T in sampled hours with an official yes/no result)
    shared by all buckets at that T (a bucket is defined on the bid, which an untradeable strike does not
    have, so the literal per-bucket denominator is undefined).  SECONDARY (diagnostic, never the gate):
    among strike-T whose last-candle ask lies in a bucket's range, the share with bid==0.  The secondary
    uses ask for CLASSIFICATION ONLY in `ask_zone_diag`, outside the P&L path.
  * Gate 2 (t) is applied to the equal-weight day-clustered t; the volume-weighted t is also reported.
  * KILL clause: every longshot cell (buckets 1..21-40 x 4 T) meeting n>=400 AND >=40 days must have
    equal-weight one-sided 97.9% upper bound on EV < +0.2c; if no cell meets the floor the clause cannot fire.

Usage:  python tail_pricing.py universe | fetch [--max-hours N] | verify | analyze
"""
from __future__ import annotations

import ast
import collections
import datetime as dt
import inspect
import json
import math
import os
import random
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import edge_sizing_v2 as V2          # normalize() is the spec-sanctioned shared parser

CACHE = os.path.join(HERE, "cache", "tail_pricing")
HOURS = os.path.join(CACHE, "hours")
OUT_JSON = os.path.join(HERE, "out", "tail_pricing.json")
OUT_MD = os.path.join(HERE, "out", "tail_pricing.md")
API = "https://api.elections.kalshi.com/trade-api/v2"
SEED = 20261027
WIN_START = "2026-08-22T00:00:00Z"
WIN_END = "2026-10-21T00:00:00Z"            # exclusive
TS = (5, 15, 30, 45)
BUCKETS = [("1", 1, 1), ("2", 2, 2), ("3", 3, 3), ("4-5", 4, 5), ("6-10", 6, 10), ("11-20", 11, 20), ("21-40", 21, 40)]
REPORT_ONLY = [("41-60", 41, 60), ("61-80", 61, 80), ("81-100", 81, 100)]
ALPHA_FAM = 28                                # 7 longshot buckets x 4 entry times
LOOKBACK_S = 75 * 60
V2.WINDOW_MIN = 80                            # normalize() keeps rows in [close-80min, close]

UA = "tail-pricing-research/1.0"
_last = [0.0]


# ------------------------------------------------------------------------------------- io helpers
def jload(p):
    with open(p) as fh:
        return json.load(fh)


def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(o, fh)
    os.replace(tmp, p)


def http(path, tries=9, gap=1.0):
    """Sequential, polite, exponential backoff on 429/5xx/network errors."""
    for i in range(tries):
        d = time.time() - _last[0]
        if d < gap:
            time.sleep(gap - d)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as fh:
                return json.load(fh)
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (400, 404):
                raise
            if i == tries - 1:
                raise
            time.sleep(min(90, 3 * 2 ** i))


def iso2ts(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def utc_day(ts):
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------- universe
def cmd_universe():
    ev = jload(os.path.join(CACHE, "events_raw.json"))
    hrs = sorted({(e["strike_date"], e["event_ticker"]) for e in ev
                  if WIN_START <= e["strike_date"] < WIN_END and e["event_ticker"].startswith("KXBTCD-")})
    hours = [{"event": t, "close_ts": iso2ts(s), "day": s[:10]} for s, t in hrs]
    jdump(hours, os.path.join(CACHE, "hours_universe.json"))
    order = [h["event"] for h in hours]
    random.Random(SEED).shuffle(order)             # shuffled ONCE, saved, never re-sorted
    jdump(order, os.path.join(CACHE, "work_order.json"))
    days = {h["day"] for h in hours}
    print("hours", len(hours), "days", len(days), flush=True)


# ------------------------------------------------------------------------------------- fetch
def split_listing(markets):
    """Write-side split.  ladder rows carry NO result; results are returned separately.  This is the only
    place in the fetch path that touches the `result` key, and it only moves it into its own file."""
    ladder, res = [], {}
    for m in markets:
        tk = m["ticker"]
        ladder.append({"ticker": tk, "close_ts": iso2ts(m["close_time"]), "floor_strike": m.get("floor_strike"),
                       "strike_type": m.get("strike_type"), "open_ts": iso2ts(m["open_time"]) if m.get("open_time") else None})
        res[tk] = m.get(RESULT_KEY)
    return ladder, res


RESULT_KEY = "result"


def _adapt(cs):
    """Historical candlesticks use {'close':..}; live ones {'close_dollars':..}.  Alias only (finality_B)."""
    out = []
    for c in cs:
        c = dict(c)
        for side in ("yes_bid", "yes_ask"):
            n = c.get(side)
            if isinstance(n, dict) and "close_dollars" not in n and "close" in n:
                n = dict(n)
                n["close_dollars"] = n["close"]
                c[side] = n
        out.append(c)
    return out


def fetch_hour(event):
    d = os.path.join(HOURS, event)
    if os.path.exists(os.path.join(d, "DONE")):
        return "cached"
    mk, cur = [], ""
    while True:
        r = http(f"/markets?event_ticker={event}&limit=1000" + (f"&cursor={cur}" if cur else ""))
        mk += r.get("markets", [])
        cur = r.get("cursor")
        if not cur:
            break
    if not mk:
        raise RuntimeError("empty listing")
    ladder, res = split_listing(mk)
    close_ts = ladder[0]["close_ts"]
    tks = [x["ticker"] for x in ladder]
    candles = {}
    for i in range(0, len(tks), 90):
        chunk = tks[i:i + 90]
        r = http("/markets/candlesticks?market_tickers=" + ",".join(chunk) +
                 f"&start_ts={close_ts - LOOKBACK_S}&end_ts={close_ts - min(TS) * 60}&period_interval=1")
        got = {m.get("market_ticker") or m.get("ticker"): m.get("candlesticks") for m in r.get("markets", [])}
        for t in chunk:
            candles[t] = got.get(t)
    jdump(ladder, os.path.join(d, "ladder.json"))
    jdump(res, os.path.join(d, "results.json"))
    jdump(candles, os.path.join(d, "candles.json"))
    jdump({"n": len(tks), "t": int(time.time())}, os.path.join(d, "DONE"))
    return "fetched"


def cmd_fetch(max_hours=None):
    order = jload(os.path.join(CACHE, "work_order.json"))
    done = fail = 0
    t0 = time.time()
    for ev in order:                                 # strictly in saved shuffled order
        if max_hours is not None and done >= max_hours:
            break
        try:
            s = fetch_hour(ev)
        except Exception as e:
            fail += 1
            print("FAIL", ev, type(e).__name__, getattr(e, "code", ""), flush=True)
            continue
        if s == "fetched":
            done += 1
            if done % 10 == 0:
                print(f"fetched {done} hours  fails {fail}  {time.time() - t0:.0f}s", flush=True)
    print("fetch finished; hours fetched this run", done, "fails", fail, flush=True)


# ------------------------------------------------------------------------------------- pricing path
# Everything from here to `pnl_step` is the PRICING PATH.  It must not read `result` (anchor b) and must not
# touch yes_ask (anchor a).
def fee_c(b_cents):
    p = b_cents / 100.0
    return math.ceil(7.0 * p * (1.0 - p) - 1e-12)


def candle_rows(raw, close_ts):
    """-> sorted [(ts, yes_bid_c, _ignored, vol)] via the shared edge_sizing_v2.normalize()."""
    if not raw:
        return []
    return sorted(V2.normalize(_adapt(raw), close_ts), key=lambda r: r[0])


def entry_quote(raw_candles, close_ts, T):
    """The ONLY entry rule: last candle at or before close - T minutes.  Returns (b_cents|None, reason, vol, stale_s).
    b is the candle's yes_bid close.  yes_bid == 0 / missing -> untradeable.  No look-around, no back-fill."""
    rows = candle_rows(raw_candles, close_ts)
    cutoff = close_ts - T * 60
    pick = None
    for ts, yb, _unused, vol in rows:
        if ts <= cutoff:
            pick = (ts, yb, vol)
    if pick is None:
        return None, "no_candle", 0.0, None
    ts, yb, vol = pick
    stale = cutoff - ts
    if yb is None or yb <= 0:
        return None, "bid_zero", vol, stale
    return int(yb), "ok", float(vol), stale


def price_hour(event):
    d = os.path.join(HOURS, event)
    ladder = jload(os.path.join(d, "ladder.json"))
    candles = jload(os.path.join(d, "candles.json"))
    out, excl = [], collections.Counter()
    for m in ladder:
        tk = m["ticker"]
        if not tk.rsplit("-", 1)[-1].startswith("T") or m.get("strike_type") not in ("greater", None):
            excl["non_T_or_non_greater_strike"] += 1
            continue
        for T in TS:
            b, why, vol, stale = entry_quote(candles.get(tk), m["close_ts"], T)
            out.append({"event": event, "ticker": tk, "close_ts": m["close_ts"], "day": utc_day(m["close_ts"]),
                        "T": T, "b": b, "why": why, "vol": vol, "stale": stale})
    return out, excl


def ask_zone_diag(event):
    """DIAGNOSTIC ONLY (not in the P&L path): classify strike-T by last-candle ask to show how many 'longshot-
    looking' strikes have no bid.  Never used for pricing."""
    d = os.path.join(HOURS, event)
    ladder = jload(os.path.join(d, "ladder.json"))
    candles = jload(os.path.join(d, "candles.json"))
    tally = collections.Counter()
    for m in ladder:
        rows = candle_rows(candles.get(m["ticker"]), m["close_ts"])
        for T in TS:
            cut = m["close_ts"] - T * 60
            pick = None
            for ts, yb, ya, vol in rows:
                if ts <= cut:
                    pick = (yb, ya)
            if pick is None or pick[1] is None:
                continue
            for name, lo, hi in BUCKETS + REPORT_ONLY:
                if lo <= pick[1] <= hi:
                    tally[(T, name, "n")] += 1
                    if not pick[0]:
                        tally[(T, name, "bid0")] += 1
    return tally


# ------------------------------------------------------------------------------------- P&L step
def pnl_step(entries, event_results):
    """FIRST AND ONLY place the official `result` is joined to entries.
    Sells 1 YES at b:   NO -> +b - fee ;  YES -> -(100-b) - fee.   Returns rows with net (cents) for priced
    sales, and counters for exclusions (no official yes/no result)."""
    priced, untrad = [], []
    excl = collections.Counter()
    for e in entries:
        r = event_results[e["event"]].get(e["ticker"])
        if r not in ("yes", "no"):
            excl["no_official_yes_no_result"] += 1
            continue
        if e["b"] is None:
            untrad.append({"T": e["T"], "day": e["day"], "event": e["event"], "why": e["why"]})
            continue
        b = e["b"]
        fee = fee_c(b)
        yes = (r == "yes")
        net = (-(100 - b) - fee) if yes else (b - fee)
        priced.append({**e, "yes": yes, "fee": fee, "net": net})
    return priced, untrad, excl


# ------------------------------------------------------------------------------------- statistics
from scipy import stats as st


def wilson(k, n, z=1.959963985):
    if n == 0:
        return None, None, None
    p = k / n
    dd = 1 + z * z / n
    c = (p + z * z / (2 * n)) / dd
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / dd
    return p, max(0.0, c - h), min(1.0, c + h)


def cluster_stats(xs, ws, gs, fam=ALPHA_FAM):
    """Weighted mean + cluster-robust (CR1, linearised ratio) SE, clusters gs.  df = G-1."""
    out = {"n": len(xs)}
    if not xs:
        return out
    sw = float(sum(ws))
    if sw <= 0:
        out["mean"] = None
        return out
    mu = sum(w * x for w, x in zip(ws, xs)) / sw
    cl = collections.defaultdict(float)
    for x, w, g in zip(xs, ws, gs):
        cl[g] += w * (x - mu)
    G = len(cl)
    out.update({"mean": mu, "G": G, "df": G - 1})
    if G < 2:
        return out
    se = math.sqrt((G / (G - 1.0)) * sum(u * u for u in cl.values()) / (sw * sw))
    out["se"] = se
    out["t"] = mu / se if se > 0 else None
    out["bar"] = float(st.t.ppf(1 - 0.05 / fam / 2, G - 1))
    out["ub979"] = mu + float(st.t.ppf(0.979, G - 1)) * se
    return out


def bucket_of(b):
    for name, lo, hi in BUCKETS + REPORT_ONLY:
        if lo <= b <= hi:
            return name
    return None


# ------------------------------------------------------------------------------------- anchors
PRICING_PATH_FUNCS = ["fee_c", "candle_rows", "entry_quote", "price_hour", "pnl_step", "bucket_of"]
NO_RESULT_FUNCS = ["fee_c", "candle_rows", "entry_quote", "price_hour", "ask_zone_diag", "bucket_of", "fetch_hour"]


def _names(node):
    s = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            s.add(n.id)
        elif isinstance(n, ast.Attribute):
            s.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            s.add(n.value)
    return s


def anchor_static_checks():
    """(a) no `100 - <ask>` anywhere in the module; no ask identifier in the pricing/P&L path.
       (b) `result` not referenced by the pricing path or by fetch_hour; the key is only read in split_listing
           via RESULT_KEY and in pnl_step / verification."""
    src = open(os.path.abspath(__file__)).read()
    tree = ast.parse(src)
    ev = {"a_100_minus_x_exprs_found_all_non_ask": 0, "a_funcs_checked": [], "b_funcs_checked": []}
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub) and isinstance(n.left, ast.Constant) \
                and n.left.value in (100, 100.0, 1, 1.0):
            nm = {x.lower() for x in _names(n.right)}
            assert not any(("ask" in x) or x in ("ya", "_ya") for x in nm), f"100-ask expression at line {n.lineno}"
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub) and isinstance(n.left, ast.Constant) \
                and n.left.value in (100, 100.0):
            ev["a_100_minus_x_exprs_found_all_non_ask"] += 1
    fdefs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for f in PRICING_PATH_FUNCS:
        nm = {x.lower() for x in _names(fdefs[f])}
        assert not any(("ask" in x) or x in ("ya", "_ya") for x in nm), f"ask referenced in {f}"
        ev["a_funcs_checked"].append(f)
    for f in NO_RESULT_FUNCS:
        nm = _names(fdefs[f])
        assert "result" not in nm and "results" not in nm and "RESULT_KEY" not in nm, f"result referenced in {f}"
        ev["b_funcs_checked"].append(f)
    # ladder.json files carry no result field
    for ev_name in os.listdir(HOURS)[:25]:
        p = os.path.join(HOURS, ev_name, "ladder.json")
        if os.path.exists(p):
            for row in jload(p)[:3]:
                assert "result" not in row
    return ev


def load_results_for(events):
    return {e: jload(os.path.join(HOURS, e, "results.json")) for e in events}


def hand_worked(entries, results, n=10):
    """First n priced T=15 entries with 1<=b<=10, in WORK ORDER (rule fixed before outcomes).  Re-parses the RAW
    candle JSON independently of normalize() to prove sale price == raw yes_bid close."""
    order = jload(os.path.join(CACHE, "work_order.json"))
    pos = {e: i for i, e in enumerate(order)}
    pick = sorted([e for e in entries if e["T"] == 15 and e["b"] is not None and 1 <= e["b"] <= 10],
                  key=lambda e: (pos[e["event"]], e["ticker"]))[:n]
    rows = []
    for e in pick:
        raw = jload(os.path.join(HOURS, e["event"], "candles.json"))[e["ticker"]]
        cutoff = e["close_ts"] - 15 * 60
        cand = [c for c in raw if c["end_period_ts"] <= cutoff]
        c = max(cand, key=lambda c: c["end_period_ts"])
        raw_bid = c["yes_bid"]["close_dollars"]
        raw_ask = c["yes_ask"]["close_dollars"]
        b_raw = int(round(float(raw_bid) * 100))
        assert b_raw == e["b"], (e["ticker"], b_raw, e["b"])
        fee = fee_c(b_raw)
        r = results[e["event"]][e["ticker"]]
        net = (-(100 - b_raw) - fee) if r == "yes" else (b_raw - fee)
        rows.append({"ticker": e["ticker"], "cutoff_ts": cutoff, "candle_end_ts": c["end_period_ts"],
                     "raw_yes_bid_close": raw_bid, "raw_yes_ask_close_shown_only_for_contrast": raw_ask,
                     "sale_price_c": b_raw, "fee_c": fee, "result": r,
                     "net_c_if_NO": b_raw - fee, "net_c_if_YES": -(100 - b_raw) - fee, "net_c_realised": net,
                     "volume_fp": c.get("volume_fp")})
    return rows


# ------------------------------------------------------------------------------------- verify (anchor d)
def cmd_verify(n=40):
    evs = [e for e in jload(os.path.join(CACHE, "work_order.json")) if os.path.exists(os.path.join(HOURS, e, "DONE"))]
    rng = random.Random(SEED + 1)
    pool = []
    for e in evs[:200]:
        pool += [(e, x["ticker"]) for x in jload(os.path.join(HOURS, e, "ladder.json"))]
    sample = rng.sample(pool, min(n, len(pool)))
    out, mism = [], 0
    for e, tk in sample:
        mine = jload(os.path.join(HOURS, e, "results.json")).get(tk)
        r = http(f"/markets/{tk}")["market"]
        ok = (r.get("result") == mine)
        mism += (not ok)
        out.append({"ticker": tk, "listing_result": mine, "single_get_result": r.get("result"),
                    "status": r.get("status"), "match": ok})
    jdump({"n": len(out), "mismatches": mism, "rows": out}, os.path.join(CACHE, "verify_d.json"))
    print("verified", len(out), "mismatches", mism)


# ------------------------------------------------------------------------------------- analyze
def cmd_analyze():
    chk = anchor_static_checks()
    hours_all = jload(os.path.join(CACHE, "hours_universe.json"))
    order = jload(os.path.join(CACHE, "work_order.json"))
    done = [e for e in order if os.path.exists(os.path.join(HOURS, e, "DONE"))]
    # completed set must be a prefix of the shuffled order, otherwise note the fraction anyway
    prefix_len = 0
    for e in order:
        if e in set(done):
            prefix_len += 1
        else:
            break
    entries, excl_pricing = [], collections.Counter()
    ask_tally = collections.Counter()
    for e in done:                                    # PRICING PASS -- no result loaded yet
        o, ex = price_hour(e)
        entries += o
        excl_pricing.update(ex)
        ask_tally.update(ask_zone_diag(e))
    results = load_results_for(done)                  # first moment results are read
    priced, untrad, excl_pnl = pnl_step(entries, results)
    hand = hand_worked(entries, results)

    # strike-T observation counts (denominator = entries with official yes/no)
    obs_T = collections.Counter()
    for e in entries:
        if results[e["event"]].get(e["ticker"]) in ("yes", "no"):
            obs_T[e["T"]] += 1
    untr_T = collections.Counter(u["T"] for u in untrad)
    untr_why = collections.Counter((u["T"], u["why"]) for u in untrad)
    stale = collections.defaultdict(list)
    for e in priced:
        stale[e["T"]].append(e["stale"])

    cells, calib = {}, []
    hour_close = {h["event"]: h["close_ts"] for h in hours_all}
    days_total = len({e["day"] for e in priced})
    for T in TS:
        for name, lo, hi in BUCKETS + REPORT_ONLY:
            xs = [p for p in priced if p["T"] == T and lo <= p["b"] <= hi]
            n = len(xs)
            k = sum(p["yes"] for p in xs)
            f, wl, wh = wilson(k, n)
            meanb = (sum(p["b"] for p in xs) / n) if n else None
            row = {"T": T, "bucket": name, "n": n, "k_yes": k, "yes_rate": f, "wilson_lo": wl, "wilson_hi": wh,
                   "mean_bid_c": meanb, "bid_inside_ci": (wl * 100 <= meanb <= wh * 100) if n else None}
            calib.append(row)
            # EV
            net = [p["net"] for p in xs]
            days = [p["day"] for p in xs]
            ew = cluster_stats(net, [1.0] * n, days)
            vw = cluster_stats(net, [p["vol"] for p in xs], days)
            hr = cluster_stats(net, [1.0] * n, [p["event"] for p in xs])
            nz = (sum(1 for p in xs if p["vol"] > 0) / n) if n else None
            U = untr_T[T] / obs_T[T] if obs_T[T] else None
            az = ask_tally.get((T, name, "n"), 0)
            zloc = (ask_tally.get((T, name, "bid0"), 0) / az) if az else None
            # per-day P&L and exposure (anchor e)
            byday = collections.defaultdict(float)
            byhour_exp = collections.defaultdict(float)
            byhour_pnl = collections.defaultdict(float)
            for p in xs:
                byday[p["day"]] += p["net"]
                byhour_exp[p["event"]] += (100 - p["b"])
                byhour_pnl[p["event"]] += p["net"]
            worst_day = min(byday.items(), key=lambda kv: kv[1]) if byday else (None, None)
            maxexp_hour = max(byhour_exp.items(), key=lambda kv: kv[1]) if byhour_exp else (None, None)
            exp_day = collections.defaultdict(float)     # simultaneous: positions within one hour overlap; hours do not
            for h, v in byhour_exp.items():
                d = utc_day(hour_close[h])
                exp_day[d] = max(exp_day[d], v)
            worst_hour = min(byhour_pnl.items(), key=lambda kv: kv[1]) if byhour_pnl else (None, None)
            gates = None
            longshot = name in [b[0] for b in BUCKETS]
            if longshot:
                g1 = bool(ew.get("mean") is not None and ew["mean"] >= 1.0 and vw.get("mean") is not None and vw["mean"] >= 1.0)
                g2 = bool(ew.get("t") is not None and ew["t"] >= ew["bar"])
                g3 = bool(n >= 400 and ew.get("G", 0) >= 40)
                g4 = bool(U is not None and U <= 0.70)
                g5 = bool(nz is not None and nz >= 0.5)
                gates = {"g1_ev_ge_1c_both": g1, "g2_t_ge_bar": g2, "g3_n400_d40": g3, "g4_untrad_le_70": g4,
                         "g5_nonzero_vol_ge_50": g5, "pass": g1 and g2 and g3 and g4 and g5}
            cells[f"{T}|{name}"] = {
                "T": T, "bucket": name, "longshot": longshot, "n": n, "days": ew.get("G", 0),
                "ev_ew": ew.get("mean"), "se_ew": ew.get("se"), "t_ew": ew.get("t"), "bar": ew.get("bar"),
                "ub979_ew": ew.get("ub979"),
                "ev_vw": vw.get("mean"), "t_vw": vw.get("t"), "vol_total": sum(p["vol"] for p in xs),
                "t_hour_clustered": hr.get("t"), "hours": hr.get("G", 0),
                "untradeable_frac_T": U, "untradeable_frac_askzone": zloc, "askzone_n": az,
                "nonzero_vol_share": nz,
                "break_even_f_c": None if meanb is None else meanb - (sum(p["fee"] for p in xs) / n),
                "worst_day": worst_day[0], "worst_day_pnl_c": worst_day[1],
                "worst_hour": worst_hour[0], "worst_hour_pnl_c": worst_hour[1],
                "max_hour_short_exposure_c": maxexp_hour[1], "max_hour_exposure_event": maxexp_hour[0],
                "max_day_simultaneous_exposure_c": max(exp_day.values()) if exp_day else None,
                "gates": gates,
            }

    # verdict
    long_cells = [c for c in cells.values() if c["longshot"]]
    passing = [c for c in long_cells if c["gates"]["pass"]]
    floor_cells = [c for c in long_cells if c["n"] >= 400 and c["days"] >= 40]
    kill = bool(floor_cells) and all(c["ub979_ew"] is not None and c["ub979_ew"] < 0.2 for c in floor_cells)
    if passing:
        verdict = "PASS"
    elif kill:
        verdict = "KILL"
    else:
        verdict = "INSUFFICIENT"
    # alt reading of gate 4 (ask-zone local fraction) -- for transparency only
    alt_pass = []
    for c in long_cells:
        g = dict(c["gates"])
        zl = c["untradeable_frac_askzone"]
        g["g4_untrad_le_70"] = bool(zl is not None and zl <= 0.70)
        if all(g[k] for k in ("g1_ev_ge_1c_both", "g2_t_ge_bar", "g3_n400_d40", "g4_untrad_le_70", "g5_nonzero_vol_ge_50")):
            alt_pass.append(f"{c['T']}|{c['bucket']}")

    # book-level tail disclosure: all longshot buckets (b<=40) pooled at each T
    book = {}
    for T in TS:
        ps = [p for p in priced if p["T"] == T and p["b"] <= 40]
        byday, byhour = collections.defaultdict(float), collections.defaultdict(float)
        expo = collections.defaultdict(float)
        for p in ps:
            byday[p["day"]] += p["net"]
            byhour[p["event"]] += p["net"]
            expo[p["event"]] += 100 - p["b"]
        exp_day = collections.defaultdict(float)
        for h, v in expo.items():
            d = utc_day(hour_close[h])
            exp_day[d] = max(exp_day[d], v)
        wd = min(byday.items(), key=lambda kv: kv[1]) if byday else (None, None)
        wh = min(byhour.items(), key=lambda kv: kv[1]) if byhour else (None, None)
        sdays = sorted(byday.values())
        book[T] = {"n": len(ps), "days": len(byday), "total_pnl_c": sum(byday.values()),
                   "mean_net_c": (sum(p["net"] for p in ps) / len(ps)) if ps else None,
                   "worst_day": wd[0], "worst_day_pnl_c": wd[1], "worst_hour": wh[0], "worst_hour_pnl_c": wh[1],
                   "best_day_pnl_c": sdays[-1] if sdays else None,
                   "max_hour_short_exposure_c": max(expo.values()) if expo else None,
                   "max_day_simultaneous_exposure_c": max(exp_day.values()) if exp_day else None,
                   "n_negative_days": sum(1 for v in byday.values() if v < 0),
                   "ev_ex_worst_day_c": (sum(byday.values()) - wd[1]) / max(1, len(ps) - sum(1 for p in ps if p["day"] == wd[0])) if ps else None}

    hours_done_days = sorted({utc_day(h["close_ts"]) for h in hours_all if h["event"] in set(done)})
    rep = {
        "spec": "TAIL_PRICING_SPEC.md", "seed": SEED, "verdict": verdict,
        "sampling": {"hours_in_universe": len(hours_all), "hours_priced": len(done),
                     "fraction": len(done) / len(hours_all), "prefix_of_shuffled_order": prefix_len,
                     "days_in_universe": len({h["day"] for h in hours_all}), "days_with_sampled_hours": len(hours_done_days),
                     "method": "whole hours, seeded shuffle (20261027), saved work_order.json, strict order, never re-sorted"},
        "counts": {"strike_T_observations_total": sum(obs_T.values()), "priced_sales_all_buckets": len(priced),
                   "obs_by_T": dict(obs_T), "untradeable_by_T": dict(untr_T),
                   "untradeable_frac_by_T": {T: untr_T[T] / obs_T[T] for T in TS if obs_T[T]},
                   "untradeable_reasons": {f"T{k[0]}:{k[1]}": v for k, v in untr_why.items()},
                   "exclusions_pricing": dict(excl_pricing), "exclusions_pnl": dict(excl_pnl),
                   "staleness_s_median_by_T": {T: sorted(stale[T])[len(stale[T]) // 2] if stale[T] else None for T in TS},
                   "staleness_s_p90_by_T": {T: sorted(stale[T])[int(len(stale[T]) * 0.9)] if stale[T] else None for T in TS}},
        "calibration": calib, "cells": cells, "book_tail_b_le_40": book,
        "pass_cells": [f"{c['T']}|{c['bucket']}" for c in passing],
        "kill_floor_cells": [f"{c['T']}|{c['bucket']}" for c in floor_cells],
        "alt_gate4_pass_cells": alt_pass,
        "anchors": {"a_b_static": chk, "hand_worked_10": hand, "d_verify": (jload(os.path.join(CACHE, "verify_d.json"))
                                                                         if os.path.exists(os.path.join(CACHE, "verify_d.json")) else None)},
        "bonferroni": {"family": ALPHA_FAM, "alpha_two_sided": 0.05 / ALPHA_FAM, "p": 1 - 0.05 / ALPHA_FAM / 2},
    }
    jdump(rep, OUT_JSON)
    write_md(rep)
    print("verdict", verdict, "hours", len(done), "/", len(hours_all), "priced", len(priced))
    return rep


# ------------------------------------------------------------------------------------- report
def _f(x, nd=2, pct=False):
    if x is None:
        return "n/a"
    return f"{x * 100:.{nd}f}%" if pct else f"{x:.{nd}f}"


def write_md(rep):
    L = []
    S, C, K = rep["sampling"], rep["counts"], rep["cells"]
    cal = rep["calibration"]
    L.append("# Tail pricing: are Kalshi BTC-hourly longshots overpriced?  (TAIL_PRICING_SPEC.md, executed)\n")
    L.append(f"**VERDICT: {rep['verdict']}**  (frozen PASS/KILL rule applied verbatim; numbers beside each bar in section 5)\n")
    L.append(f"Sample: {S['hours_priced']} of {S['hours_in_universe']} hourly events ({S['fraction']*100:.1f}%), "
             f"{S['days_with_sampled_hours']} of {S['days_in_universe']} UTC days; {C['strike_T_observations_total']//4:,} strikes, "
             f"{C['strike_T_observations_total']:,} strike-T observations, {C['priced_sales_all_buckets']:,} priced sales (all buckets).\n")
    L.append("## 0. Plain reading (written after the run; numbers are from the tables below)\n")
    L.append("* **Calibrated, not overpriced.** Of 28 longshot cells (7 buckets x 4 T) the mean executable bid lies inside the realised-rate Wilson 95% CI in 27; the one exception is T=30, 6-10c (rate 3.94% vs bid 7.83c). There is no monotone favourite-longshot gap: signs of (rate - bid) flip across buckets and across T.")
    L.append("* **No cell clears EV or the Bonferroni bar.** Best t anywhere is +2.15 (T=30, 6-10c, EV +2.89c, n=330 < 400 floor, bar 3.27); its neighbours in T are +1.58c (T=15), -0.18c (T=45), -2.96c (T=5), i.e. consistent with noise. Pooled over all sales at bid <= 40c, mean net is negative at every T (-1.16, -0.17, -0.69, -1.13 c/contract at T=5/15/30/45).")
    L.append("* **The 1c fee is the whole edge.** ceil(7p(1-p)) = 1c for any bid up to 17c, so selling at 1c can never net more than 0 (NO) and selling at 2-3c nets at most 1-2c against a 98-100c loss.")
    L.append("* **Untradeable fraction is ~45-48% of strike-T observations, all of it yes_bid = 0 (zero 'no candle').** It is concentrated in the dead tail: among strikes whose last ask is 1c, 100% have bid 0; at ask 2c 11-37%; at ask 3c 0-13%; above that under 5%. The 95% untradeable pattern that closed weather does NOT replicate beyond the 1c tail here; the ladder has real two-sided quotes from 2c up.")
    L.append("* **Verdict is INSUFFICIENT, and it is structural, not a coverage shortfall.** The frozen KILL clause needs a 97.9% upper bound < +0.2c in every n>=400 cell; cells at 6-40c have a day-clustered SE of 1.5-2.6c (binary payoff of +b vs -(100-b)), so even at 100% coverage (SE shrinks by ~sqrt(0.357) = 0.6x) the bound stays above +0.2c (e.g. T=45, 6-10c: -0.18 + 2.1 x 0.9 ~ 1.7c). The clause is practically unfireable above ~5c. In substance: no evidence of exploitable overpricing, point estimates are negative, and no PASS was close.")
    L.append("* **Mirror observation (outside the frozen family, untested as a strategy):** at bid >= 81c the realised YES rate exceeds the bid by ~1.0c in every T (99.77-99.95% vs ~98.9c), so SELLING favourites loses ~2c/contract (t about -55 to -180). That is the other side of the same book; testing a BUY of YES would require the ask and was not run here.")
    L.append("* **Caveats:** 35.7% of hours (503 of 1408; all 60 days covered) -- the stop was a wall-clock budget fixed before looking at results, API throughput was ~3-6 hours/minute-block under 429s. Entry uses the literal 'last candle at or before close-T' rule; candles are sparse for quiet strikes so the median candle age is 60s but p90 is 540-1140s, i.e. some quotes are up to ~19 min old; staleness sensitivity was not run (no filter is permitted). A 6-hour smoke test of the pipeline (first rows of the calibration printed, ~2k entries) was run before the full fetch; nothing in the code changed in response to it other than report formatting.\n")
    L.append("## 1. Anchor (c): calibration table (reported whatever the verdict)\n")
    L.append("Realised YES rate with Wilson 95% CI, against the executable `yes_bid` the seller receives. "
             "`gap` = realised rate minus mean bid, in cents of probability: **gap < 0 means the market overprices YES (selling is favourable before fee)**. "
             "CIs treat strikes as independent (they are not: one BTC move hits every strike of an hour), so they are too narrow; the day-clustered t in section 2 is the gate.\n")
    for T in TS:
        L.append(f"\n### T = {T} minutes before close\n")
        L.append("| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |")
        L.append("|---|---:|---:|---:|---|---:|---:|:--:|")
        for r in cal:
            if r["T"] != T:
                continue
            tag = "" if r["bucket"] in [b[0] for b in BUCKETS] else " (not a longshot; report only)"
            if r["n"]:
                gap = r["yes_rate"] * 100 - r["mean_bid_c"]
                L.append(f"| {r['bucket']}c{tag} | {r['n']:,} | {r['k_yes']:,} | {_f(r['yes_rate'],2,True)} | "
                         f"[{_f(r['wilson_lo'],2,True)}, {_f(r['wilson_hi'],2,True)}] | {r['mean_bid_c']:.2f}c | {gap:+.2f} | {'yes' if r['bid_inside_ci'] else 'NO'} |")
            else:
                L.append(f"| {r['bucket']}c{tag} | 0 | 0 | n/a | n/a | n/a | n/a | n/a |")
    L.append("\n## 2. EV table per cell (selling 1 YES at `yes_bid`, fee-inclusive, cents per contract)\n")
    L.append(f"Bonferroni: 28 comparisons, two-sided alpha = {rep['bonferroni']['alpha_two_sided']:.5f}, bar = Student-t quantile at p = {rep['bonferroni']['p']:.5f} on df = (distinct days - 1). "
             "t is signed and day-clustered (equal-weight). `U_T` = entry-time-level untradeable fraction (primary gate-4 reading). "
             "`U_ask` = diagnostic: share with bid=0 among strikes whose last-candle ask falls in the bucket range. `nz-vol` = share of priced entries with non-zero volume in the entry candle.\n")
    L.append("| T | bucket | n | days | EV eq-wt | EV vol-wt | t (eq) | bar | t (vol) | t (hour-clust) | UB97.9% | U_T | U_ask | nz-vol | PASS gates 1/2/3/4/5 |")
    L.append("|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|")
    for T in TS:
        for name, _, _ in BUCKETS:
            c = K[f"{T}|{name}"]
            g = c["gates"]
            gs = "/".join("Y" if g[k] else "n" for k in ("g1_ev_ge_1c_both", "g2_t_ge_bar", "g3_n400_d40", "g4_untrad_le_70", "g5_nonzero_vol_ge_50"))
            L.append(f"| {T} | {name} | {c['n']:,} | {c['days']} | {_f(c['ev_ew'])} | {_f(c['ev_vw'])} | {_f(c['t_ew'])} | {_f(c['bar'])} | {_f(c['t_vw'])} | "
                     f"{_f(c['t_hour_clustered'])} | {_f(c['ub979_ew'])} | {_f(c['untradeable_frac_T'],1,True)} | {_f(c['untradeable_frac_askzone'],1,True)} | {_f(c['nonzero_vol_share'],1,True)} | {gs} |")
    L.append("\nAbove-40c buckets (reported, cannot PASS):\n")
    L.append("| T | bucket | n | days | EV eq-wt | EV vol-wt | t (eq) |")
    L.append("|--:|---|--:|--:|--:|--:|--:|")
    for T in TS:
        for name, _, _ in REPORT_ONLY:
            c = K[f"{T}|{name}"]
            L.append(f"| {T} | {name} | {c['n']:,} | {c['days']} | {_f(c['ev_ew'])} | {_f(c['ev_vw'])} | {_f(c['t_ew'])} |")
    L.append("\n## 3. Untradeable fraction (what closed weather)\n")
    L.append("| T | strike-T obs | untradeable | fraction | no candle | bid = 0 | median candle age at entry (s, priced) | p90 age (s) |")
    L.append("|--:|--:|--:|--:|--:|--:|--:|--:|")
    for T in TS:
        L.append(f"| {T} | {C['obs_by_T'].get(T,0):,} | {C['untradeable_by_T'].get(T,0):,} | {_f(C['untradeable_frac_by_T'].get(T),1,True)} | "
                 f"{C['untradeable_reasons'].get(f'T{T}:no_candle',0):,} | {C['untradeable_reasons'].get(f'T{T}:bid_zero',0):,} | "
                 f"{C['staleness_s_median_by_T'].get(T)} | {C['staleness_s_p90_by_T'].get(T)} |")
    L.append("\n## 4. Anchor (e): tail risk (sold-tail P&L is many small wins and few large losses)\n")
    L.append("Per cell, over SAMPLED hours only (the sample is a random subset of hours; a full-universe day would hold about "
             f"{1/S['fraction']:.1f}x as many positions, so absolute day losses are understated by roughly that factor). "
             "Positions in one hourly event are open simultaneously; different hours do not overlap (T <= 45 < 60), so max simultaneous short exposure per day = largest single-hour sum of (100 - bid) over that day's sold strikes, i.e. collateral at risk, in cents (100c = $1).\n")
    L.append("| T | bucket | n | worst day (UTC) | worst-day P&L (c) | worst hour P&L (c) | max hour short exposure (c) | max day simultaneous exposure (c) |")
    L.append("|--:|---|--:|---|--:|--:|--:|--:|")
    for T in TS:
        for name, _, _ in BUCKETS:
            c = K[f"{T}|{name}"]
            L.append(f"| {T} | {name} | {c['n']:,} | {c['worst_day']} | {_f(c['worst_day_pnl_c'],0)} | {_f(c['worst_hour_pnl_c'],0)} | "
                     f"{_f(c['max_hour_short_exposure_c'],0)} | {_f(c['max_day_simultaneous_exposure_c'],0)} |")
    L.append("\nBook view: ALL longshot sales (bid <= 40c) pooled at each T:\n")
    L.append("| T | n | days | mean net (c/contract) | total P&L (c) | worst day | worst-day P&L (c) | best day (c) | negative days | mean net excl. worst day (c) | worst hour P&L (c) | max day simult. exposure (c) |")
    L.append("|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|")
    for T, b in rep["book_tail_b_le_40"].items():
        L.append(f"| {T} | {b['n']:,} | {b['days']} | {_f(b['mean_net_c'],3)} | {_f(b['total_pnl_c'],0)} | {b['worst_day']} | {_f(b['worst_day_pnl_c'],0)} | "
                 f"{_f(b['best_day_pnl_c'],0)} | {b['n_negative_days']} | {_f(b['ev_ex_worst_day_c'],3)} | {_f(b['worst_hour_pnl_c'],0)} | {_f(b['max_day_simultaneous_exposure_c'],0)} |")
    L.append("\n## 5. Verdict: frozen rule, numbers beside each bar\n")
    long_cells = [c for c in K.values() if c["longshot"]]
    floor = [c for c in long_cells if c["n"] >= 400 and c["days"] >= 40]
    pool = floor if floor else [c for c in long_cells if c["n"] > 0]
    best = max(pool, key=lambda c: c["ev_ew"]) if pool else None
    L.append(f"* Cells meeting the n floor (n >= 400 priced sales AND >= 40 distinct days): **{len(floor)} of 28** ({', '.join(rep['kill_floor_cells']) or 'none'}).")
    L.append(f"* PASS cells (all five gates): **{len(rep['pass_cells'])}** ({', '.join(rep['pass_cells']) or 'none'}).")
    if best:
        g = best["gates"]
        L.append(f"* Best longshot cell by equal-weight EV among {'floor-meeting' if floor else 'all populated'} cells: **T={best['T']}, bucket {best['bucket']}c**, n={best['n']:,}, {best['days']} days.")
        L.append(f"  * Gate 1 (EV >= +1.0c both readings): equal-weight {_f(best['ev_ew'])}c, volume-weighted {_f(best['ev_vw'])}c -> {'met' if g['g1_ev_ge_1c_both'] else 'NOT met'}.")
        L.append(f"  * Gate 2 (signed day-clustered t >= bar): t = {_f(best['t_ew'])} vs bar {_f(best['bar'])} -> {'met' if g['g2_t_ge_bar'] else 'NOT met'}.")
        L.append(f"  * Gate 3 (n >= 400 across >= 40 days): n = {best['n']:,}, days = {best['days']} -> {'met' if g['g3_n400_d40'] else 'NOT met'}.")
        L.append(f"  * Gate 4 (untradeable <= 70%): U_T = {_f(best['untradeable_frac_T'],1,True)} (diagnostic ask-zone: {_f(best['untradeable_frac_askzone'],1,True)}) -> {'met' if g['g4_untrad_le_70'] else 'NOT met'}.")
        L.append(f"  * Gate 5 (>= 50% non-zero entry-candle volume): {_f(best['nonzero_vol_share'],1,True)} -> {'met' if g['g5_nonzero_vol_ge_50'] else 'NOT met'}.")
        L.append(f"  * KILL clause for this cell: 97.9% one-sided upper bound on EV = {_f(best['ub979_ew'])}c vs +0.2c.")
    L.append("\nKILL clause (every floor-meeting cell must have one-sided 97.9% UB on EV < +0.2c):\n")
    L.append("| T | bucket | n | days | EV eq-wt | SE | UB 97.9% | < +0.2c |")
    L.append("|--:|---|--:|--:|--:|--:|--:|:--:|")
    for c in floor:
        L.append(f"| {c['T']} | {c['bucket']} | {c['n']:,} | {c['days']} | {_f(c['ev_ew'])} | {_f(c['se_ew'],3)} | {_f(c['ub979_ew'])} | {'yes' if c['ub979_ew'] < 0.2 else 'NO'} |")
    if not floor:
        L.append("| (no cell meets the n floor: the KILL clause cannot fire) | | | | | | | |")
    L.append(f"\nAlternate (secondary) reading of gate 4 with the ask-zone fraction would pass: {', '.join(rep['alt_gate4_pass_cells']) or 'no cell'}.\n")
    L.append("## 6. Anchors (a), (b), (d)\n")
    a = rep["anchors"]
    L.append(f"**(a) Executable side.** Static AST scan of this module passed: no subtraction `100 - <expression referencing ask>` exists anywhere; the pricing/P&L functions {a['a_b_static']['a_funcs_checked']} reference no ask identifier at all (the 4th tuple field from `edge_sizing_v2.normalize()` is bound to `_unused`). "
             "Sale price = `yes_bid.close_dollars` of the last candle at or before close-T; hand-worked entries below were re-parsed from raw candle JSON independently of `normalize()` and asserted equal to the price used. The raw ask is printed only as a contrast column; it enters no formula.\n")
    L.append("| ticker | candle end (cutoff = candle end?) | raw yes_bid close | raw yes_ask (not used) | sale price b | fee | result | net if NO = b-fee | net if YES = -(100-b)-fee | realised |")
    L.append("|---|---|--:|--:|--:|--:|---|--:|--:|--:|")
    for h in a["hand_worked_10"]:
        L.append(f"| {h['ticker']} | {h['candle_end_ts']} ({'=' if h['candle_end_ts']==h['cutoff_ts'] else 'before'}) | {h['raw_yes_bid_close']} | {h['raw_yes_ask_close_shown_only_for_contrast']} | {h['sale_price_c']} | {h['fee_c']} | {h['result']} | {h['net_c_if_NO']} | {h['net_c_if_YES']} | {h['net_c_realised']} |")
    L.append(f"\n**(b) No outcome conditioning.** Fetch writes `ladder.json` (no result field) and `results.json` separately. The pricing pass (`price_hour`, `entry_quote`, `ask_zone_diag`, `fee_c`, `candle_rows`, `bucket_of`, `fetch_hour`) is asserted by AST scan to reference neither `result` nor `results`; results are first loaded after all entries are priced, and joined only in `pnl_step`. Functions checked: {a['a_b_static']['b_funcs_checked']}. Every entry was priced before any outcome was loaded. Entry selection is the single frozen rule (last candle at or before close-T); there is no search.\n")
    d = a["d_verify"]
    if d:
        L.append(f"**(d) Settlement provenance.** Official `result` field only (never self-computed). Spot-check: {d['n']} randomly chosen strikes (seeded) re-read via `GET /markets/{{ticker}}`: **{d['mismatches']} mismatches**.\n")
    else:
        L.append("**(d)** spot-check not run.\n")
    L.append("## 7. Exclusions and sampling\n")
    L.append(f"* Sampling: {S['method']}. Hours priced {S['hours_priced']} / {S['hours_in_universe']} = {S['fraction']*100:.1f}%; completed set is a {'contiguous prefix' if S['prefix_of_shuffled_order']==S['hours_priced'] else 'NON-prefix subset'} of the shuffled order ({S['prefix_of_shuffled_order']} leading hours). Days touched {S['days_with_sampled_hours']} / {S['days_in_universe']}.")
    L.append(f"* Exclusions in pricing (non -T / non-greater strikes): {C['exclusions_pricing'] or 'none'}.")
    L.append(f"* Exclusions at P&L step (no official yes/no `result`, counted per strike-T entry): {C['exclusions_pnl'] or 'none'}.")
    L.append(f"* Untradeable entries (no candle or bid = 0) are kept in every denominator and never priced or back-filled: {sum(C['untradeable_by_T'].values()):,} of {C['strike_T_observations_total']:,} strike-T observations.")
    L.append("* Calendar day = UTC date of close. Universe window: closes 2026-08-22T00:00Z to 2026-10-20T23:59Z (60 days).")
    L.append("* Spec-silent choices fixed before outcomes were read are listed in the docstring of `tail_pricing.py`.")
    open(OUT_MD, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    if c == "universe":
        cmd_universe()
    elif c == "fetch":
        mh = int(sys.argv[sys.argv.index("--max-hours") + 1]) if "--max-hours" in sys.argv else None
        cmd_fetch(mh)
    elif c == "verify":
        cmd_verify()
    elif c == "analyze":
        cmd_analyze()
