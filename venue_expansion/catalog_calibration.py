"""catalog_calibration.py -- executes CATALOG_CALIBRATION_SPEC.md (registered 2026-10-29).  Nothing here may move a bar.

QUESTION. Is there ANY corner of Kalshi where the executable price and the realised YES frequency differ by more
than the fee?  Calibration, not strategy: for every (category x price bucket x direction x entry time) cell, the
realised frequency f of YES is compared with the price the taker would actually have paid / received.

EXECUTABLE RULE (asserted by AST scan of this whole module, anchor c):
  Buying YES  executes at yes_ask.  Edge iff 100*f > yes_ask + fee.
  Selling YES executes at yes_bid.  Edge iff 100*f < yes_bid - fee.      fee = ceil(7p(1-p)) cents at the crossing price.
  `100 - yes_ask` is computed NOWHERE.  No mid price is computed anywhere.
  A market-minute missing the relevant side is UNTRADEABLE: counted in the denominator, never priced, never back-filled.

NO OUTCOME IN THE ENTRY PATH (anchor d): the fetch step writes markets.json (no result) and results.json separately;
the pricing pass never opens results.json.  AST scan + a negative control on a doctored copy that must raise.

INTERPRETATION CHOICES FIXED BEFORE ANY OUTCOME WAS READ (the spec is silent; recorded here, never revisited):
  * Sampling: whole EVENTS.  One stream per category (+ an ANCHOR stream = every KXBTCD event, which is removed from the
    Crypto stream so the two are disjoint).  Each stream is sorted by event ticker, then shuffled ONCE with
    random.Random(20261029) in the fixed stream order [ANCHOR, Sports, Politics, Financials, Economics,
    Climate and Weather, Commodities, Crypto], and saved (streams.json, rr_order.json).  The 7 category streams are
    processed round-robin in the saved interleaved order; ANCHOR first.  Never re-sorted.  Coverage per stream =
    done / universe, and whether the done set is an exact prefix of the saved order.
  * Entry: last candle with end_period_ts <= close - T*60, T in {15, 60}, no older than STALE_CAP_MIN (120 min) before
    the cutoff.  No candle in that window => untradeable ("no_candle"), kept in the denominator.  The cap is the
    definition of "a quote exists at this entry time"; it is not a search over minutes.
  * yes_bid == 0 / missing => no bid (sell untradeable).  yes_ask == 0 / missing / >= 100 => no ask (buy untradeable);
    Kalshi shows an EMPTY ask side as 1.0000 (see previous_yes_ask_dollars on any thin market), and a buy at 100c can
    never have edge.  Prices 99 (and ask/bid at 99) lie outside every frozen bucket and are counted, not priced.
  * A market not yet trading at the cutoff (open_time >= cutoff, so no candle can end at or before it) is not an observation at that T: EXCLUDED with a
    count (primary).  The strict reading (kept as untradeable in the denominator) is also reported for gate 3.
  * Cluster unit: event.  Calendar day = UTC date of close_time.  The PASS/KILL gate uses the literal Wilson interval on
    observations (as the spec says); event-clustered and day-clustered design-effect-adjusted Wilson intervals are
    reported beside it as a robustness column, and are never used to flip a verdict silently.
  * Cell comparison price = cell mean of the executable price (mean ask for buy, mean bid for sell); fee = cell mean of
    the per-observation fee.  PASS: buy LB > (mean ask + mean fee)/100 ; sell UB < (mean bid - mean fee)/100.
  * Untradeable fraction for gate 3 (a bucket is defined on a price an untradeable observation does not have): the
    (category, T, direction)-level fraction = observations lacking the relevant side / all observations with an
    official yes/no result and an open market, exactly as TAIL_PRICING defined U_T.
  * Anchor (a) pass rule, fixed now: (a1) the T=15 table re-derived from the cached TAIL_PRICING hours through THIS
    module's code reproduces TAIL_PRICING's published n and YES counts in all 7 longshot buckets; (a2) on the fresh
    KXBTCD stratum, >= 80% of sell-direction longshot cells (frozen buckets <= 40c, T in {15,60}, n >= 30) have the mean
    executable bid inside the 95% Wilson interval (TAIL_PRICING's yardstick; it found 27 of 28).

Usage:  python catalog_calibration.py universe | fetch STREAM|RR [--max-events N] [--budget-s S] | replicate |
                                       verify | analyze
"""
from __future__ import annotations

import ast
import collections
import datetime as dt
import json
import math
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shape_screen as SS               # catalog / http / paging machinery (reused, not rebuilt)
import tail_pricing as TP               # fee, wilson, _adapt, iso2ts, utc_day, cache layout of the anchor hours
import edge_sizing_v2 as V2             # normalize(): the spec-sanctioned shared candle parser
from scipy import stats as st

V2.WINDOW_MIN = 600                      # normalize() keeps rows in [close-600min, close]; the cutoff rule below selects
CACHE = os.path.join(HERE, "cache", "catalog_calib")
EVDIR = os.path.join(CACHE, "events")
OUT_JSON = os.path.join(HERE, "out", "catalog_calibration.json")
OUT_MD = os.path.join(HERE, "out", "catalog_calibration.md")
TP_HOURS = os.path.join(HERE, "cache", "tail_pricing", "hours")      # READ ONLY
API = SS.API
SEED = 20261029
LIVE_CUT = "2026-08-29T00:00:00Z"
TS = (15, 60)
STALE_CAP_MIN = 120
FETCH_BACK_MIN = 60 + STALE_CAP_MIN + 1
CHUNK = 40
CATS = ["Sports", "Politics", "Financials", "Economics", "Climate and Weather", "Commodities", "Crypto"]
STREAMS = ["ANCHOR"] + CATS
ANCHOR_SERIES = "KXBTCD"
BUCKETS = [("1-2", 1, 2), ("3-5", 3, 5), ("6-10", 6, 10), ("11-20", 11, 20), ("21-40", 21, 40),
           ("41-59", 41, 59), ("60-79", 60, 79), ("80-89", 80, 89), ("90-94", 90, 94), ("95-98", 95, 98)]
LONGSHOT = {"1-2", "3-5", "6-10", "11-20", "21-40"}
TP_BUCKETS = [("1", 1, 1), ("2", 2, 2), ("3", 3, 3), ("4-5", 4, 5), ("6-10", 6, 10), ("11-20", 11, 20), ("21-40", 21, 40)]
DIRS = ("buy", "sell")
N_COMP = len(BUCKETS) * len(DIRS) * len(TS) * len(CATS)             # 280
ALPHA = 0.05 / N_COMP
Z_GATE = float(st.norm.ppf(1 - ALPHA / 2))                         # 99.982% two-sided
Z95 = 1.959963985
RESULT_KEY = "result"


# ---------------------------------------------------------------------------------------------------- helpers
def jload(p):
    with open(p) as fh:
        return json.load(fh)


def jdump(o, p):
    SS.jdump(o, p)


def http(path, tries=6):
    return SS.http_get(API + path, tries=tries)


def fee_c(price_c):
    return TP.fee_c(price_c)


def bucket_of(price, buckets=BUCKETS):
    for name, lo, hi in buckets:
        if lo <= price <= hi:
            return name
    return None


# ---------------------------------------------------------------------------------------------------- universe
def cmd_universe():
    seen, ev = set(), []
    for line in open(os.path.join(CACHE, "events_all.jsonl")):
        d = json.loads(line)
        if d["e"] in seen:
            continue
        seen.add(d["e"])
        ev.append(d)
    cnt_all = collections.Counter(d["c"] for d in ev)
    # UNIVERSE LIMIT (disclosed): the settled-event walk is newest-first and was stopped once ~1,000 consecutive events had
    # last_updated < the live/historical cutoff (those are the bulk-migrated pre-2026-08-29 events, served only by the
    # per-market /historical endpoints at ~1 call per market).  The universe is therefore the LIVE-PARTITION events in the
    # walked prefix: last_updated_ts >= LIVE_CUT.
    hist_band = [d for d in ev if (d.get("lu") or "") < LIVE_CUT]
    ev = [d for d in ev if (d.get("lu") or "") >= LIVE_CUT]
    mve = [d for d in ev if d["e"].startswith("KXMVE") and d["c"] in CATS]
    keep = [d for d in ev if d["c"] in CATS and not d["e"].startswith("KXMVE")]
    streams = {s: [] for s in STREAMS}
    for d in keep:
        if d["s"] == ANCHOR_SERIES:
            streams["ANCHOR"].append(d["e"])
        else:
            streams[d["c"]].append(d["e"])
    rng = random.Random(SEED)
    for s in STREAMS:
        streams[s].sort()                       # deterministic base order, then ONE seeded shuffle; saved; never re-sorted
        rng.shuffle(streams[s])
    # interleave the 7 category streams round-robin (ANCHOR is run first, on its own)
    rr, idx = [], {s: 0 for s in CATS}
    while any(idx[s] < len(streams[s]) for s in CATS):
        for s in CATS:
            if idx[s] < len(streams[s]):
                rr.append([s, streams[s][idx[s]]])
                idx[s] += 1
    meta = {e["e"]: {"c": e["c"], "s": e["s"], "me": e.get("me")} for e in keep}
    jdump(streams, os.path.join(CACHE, "streams.json"))
    jdump(rr, os.path.join(CACHE, "rr_order.json"))
    jdump(meta, os.path.join(CACHE, "event_meta.json"))
    jdump({"events_walked": len(ev), "by_category_all": dict(cnt_all), "kept": {s: len(streams[s]) for s in STREAMS},
           "excluded_mve_in_scope_categories": len(mve), "excluded_historical_band_lu_before_cut": len(hist_band),
           "historical_band_by_category": dict(collections.Counter(d["c"] for d in hist_band)), "live_cut": LIVE_CUT, "seed": SEED}, os.path.join(CACHE, "universe_summary.json"))
    print("events walked", len(ev), "kept", {s: len(streams[s]) for s in STREAMS}, "mve excluded", len(mve), flush=True)


# ---------------------------------------------------------------------------------------------------- fetch
def paged(path):
    out, cur = [], ""
    while True:
        r = http(path + (f"&cursor={cur}" if cur else ""))
        out += r.get("markets", [])
        cur = r.get("cursor")
        if not cur:
            return out


def split_listing(markets, part):
    """The ONLY place in the fetch path that reads the official `result` key; it only moves it into its own file."""
    ladder, res = [], {}
    for m in markets:
        tk = m["ticker"]
        ladder.append({"ticker": tk, "event": m.get("event_ticker"), "part": part,
                       "close_ts": TP.iso2ts(m["close_time"]) if m.get("close_time") else None,
                       "open_ts": TP.iso2ts(m["open_time"]) if m.get("open_time") else None,
                       "status": m.get("status"), "strike_type": m.get("strike_type"), "mtype": m.get("market_type"),
                       "vol_final": m.get("volume_fp")})
        res[tk] = m.get(RESULT_KEY)
    return ladder, res


def fetch_event(ev):
    d = os.path.join(EVDIR, ev)
    if os.path.exists(os.path.join(d, "DONE")):
        return "cached"
    mk = paged(f"/markets?event_ticker={ev}&limit=1000")
    part = "live"
    if not mk:
        mk = paged(f"/historical/markets?event_ticker={ev}&limit=1000")
        part = "hist"
    ladder, res = split_listing(mk, part)
    ladder = [x for x in ladder if x["close_ts"]]
    candles, api_calls = {}, 0
    if part == "live":
        groups = collections.defaultdict(list)
        for x in ladder:
            groups[x["close_ts"]].append(x["ticker"])
        for close_ts, tks in groups.items():
            for i in range(0, len(tks), CHUNK):
                chunk = tks[i:i + CHUNK]
                r = http("/markets/candlesticks?market_tickers=" + ",".join(chunk) +
                         f"&start_ts={close_ts - FETCH_BACK_MIN * 60}&end_ts={close_ts - min(TS) * 60}&period_interval=1")
                api_calls += 1
                got = {m.get("market_ticker") or m.get("ticker"): m.get("candlesticks") for m in r.get("markets", [])}
                for t in chunk:
                    candles[t] = got.get(t)
    else:
        for x in ladder:
            a, b = x["close_ts"] - FETCH_BACK_MIN * 60, x["close_ts"] - min(TS) * 60
            if x["open_ts"] and x["open_ts"] > b:
                candles[x["ticker"]] = []
                continue
            try:
                r = http(f"/historical/markets/{x['ticker']}/candlesticks?start_ts={a}&end_ts={b}&period_interval=1")
                candles[x["ticker"]] = r.get("candlesticks", [])
            except Exception:
                candles[x["ticker"]] = None
            api_calls += 1
    jdump(ladder, os.path.join(d, "markets.json"))
    jdump(res, os.path.join(d, "results.json"))
    jdump(candles, os.path.join(d, "candles.json"))
    jdump({"n": len(ladder), "part": part, "t": int(time.time()), "calls": api_calls}, os.path.join(d, "DONE"))
    return "fetched"


def cmd_fetch(stream, max_events=None, budget_s=None):
    streams = jload(os.path.join(CACHE, "streams.json"))
    order = [[stream, e] for e in streams[stream]] if stream != "RR" else jload(os.path.join(CACHE, "rr_order.json"))
    t0 = time.time()
    done = fail = 0
    failed = []
    for s, ev in order:
        if os.path.exists(os.path.join(EVDIR, ev, "DONE")):
            continue
        if max_events is not None and done >= max_events:
            break
        if budget_s is not None and time.time() - t0 > budget_s:
            break
        try:
            fetch_event(ev)
            done += 1
        except Exception as e:
            fail += 1
            failed.append(ev)
            print("FAIL", s, ev, type(e).__name__, str(e)[:80], flush=True)
            continue
        if done % 10 == 0:
            print(f"[{stream}] fetched {done}  fails {fail}  {time.time() - t0:.0f}s  stats={SS.STATS}", flush=True)
    for ev in failed:                                    # retry failures in place so a prefix is not left with holes
        try:
            fetch_event(ev)
            done += 1
        except Exception as e:
            print("FAIL-AGAIN", ev, str(e)[:80], flush=True)
    print(f"fetch finished [{stream}]: fetched {done} fails {fail} in {time.time() - t0:.0f}s", flush=True)


# ---------------------------------------------------------------------------------------------------- pricing path
# Everything from here to `join_results` is the PRICING PATH: it must never read `result`, must never compute 100-ask,
# and must never compute a mid price.
def candle_rows(raw, close_ts):
    """-> sorted [(ts, yes_bid_c, yes_ask_c, vol)] via the shared edge_sizing_v2.normalize()."""
    if not raw:
        return []
    return sorted(V2.normalize(TP._adapt(raw), close_ts), key=lambda r: r[0])


def entry_sides(raw, close_ts, open_ts, T, floor_ts=None):
    """THE entry rule: last candle with end_period_ts <= close - T*60 (and >= floor).  Returns a dict with the two quoted
    sides exactly as printed on that candle.  No look-around, no back-fill, no search over minutes."""
    cutoff = close_ts - T * 60
    if open_ts is not None and open_ts >= cutoff:
        return {"why": "not_open", "bid": None, "ask": None, "vol": 0.0, "stale": None, "cts": None}
    if floor_ts is None:
        floor_ts = cutoff - STALE_CAP_MIN * 60
    pick = None
    for ts, yes_bid, yes_ask, vol in candle_rows(raw, close_ts):
        if floor_ts <= ts <= cutoff:
            pick = (ts, yes_bid, yes_ask, vol)
    if pick is None:
        return {"why": "no_candle", "bid": None, "ask": None, "vol": 0.0, "stale": None, "cts": None}
    ts, yes_bid, yes_ask, vol = pick
    bid = int(yes_bid) if (yes_bid is not None and yes_bid > 0) else None
    ask = int(yes_ask) if (yes_ask is not None and 0 < yes_ask < 100) else None
    return {"why": "ok", "bid": bid, "ask": ask, "vol": float(vol), "stale": cutoff - ts, "cts": ts}


def exec_price(entry, direction):
    """Buying YES executes at the ask; selling YES executes at the bid.  Nothing else is ever used."""
    if direction == "buy":
        return entry["ask"]
    if direction == "sell":
        return entry["bid"]
    raise ValueError(direction)


def price_event(ev, root=EVDIR):
    d = os.path.join(root, ev)
    ladder = jload(os.path.join(d, "markets.json"))
    candles = jload(os.path.join(d, "candles.json"))
    out = []
    for m in ladder:
        raw = candles.get(m["ticker"])
        for T in TS:
            e = entry_sides(raw, m["close_ts"], m["open_ts"], T)
            e.update({"event": ev, "ticker": m["ticker"], "close_ts": m["close_ts"], "day": TP.utc_day(m["close_ts"]),
                      "T": T, "fetch_none": raw is None})
            out.append(e)
    return out


# ---------------------------------------------------------------------------------------------------- join (first and only place `result` is read)
def join_results(entries, results_by_event):
    """Attach the official result.  Returns (rows, exclusions).  Rows keep not-open entries flagged, never priced."""
    rows, excl = [], collections.Counter()
    for e in entries:
        r = results_by_event[e["event"]].get(e["ticker"])
        if r not in ("yes", "no"):
            excl[f"no_official_yes_no_result:{r!r}"] += 1
            continue
        rows.append(dict(e, y=1 if r == "yes" else 0))
    return rows, excl


# ---------------------------------------------------------------------------------------------------- statistics
def wilson(k, n, z):
    if n == 0:
        return (None, None, None)
    return TP.wilson(k, n, z)


def wilson_cluster(ys, groups, z):
    """Design-effect-adjusted Wilson: the CR1 cluster-robust variance of the proportion over the binomial variance."""
    n = len(ys)
    if n == 0:
        return (None, None, None, None)
    k = sum(ys)
    p = k / n
    cl = collections.defaultdict(float)
    for y, g in zip(ys, groups):
        cl[g] += y - p
    G = len(cl)
    vb = p * (1 - p) / n
    if G < 2 or vb <= 0:
        lo, hi = wilson(k, n, z)[1:]
        return (lo, hi, 1.0, float(n))
    vc = (G / (G - 1.0)) * sum(u * u for u in cl.values()) / (n * n)
    deff = max(1.0, vc / vb)
    ne = n / deff
    _, lo, hi = TP.wilson(p * ne, ne, z)
    return (lo, hi, deff, ne)


def cell_stats(obs, untrad_frac, direction, strict_untrad):
    """obs: list of dicts {price, y, event, day, vol}.  Pure frequencies; no EV t-statistic anywhere."""
    n = len(obs)
    c = {"n": n, "untradeable_frac": untrad_frac, "untradeable_frac_strict": strict_untrad}
    if n == 0:
        return c
    k = sum(o["y"] for o in obs)
    mp = sum(o["price"] for o in obs) / n
    mf = sum(fee_c(o["price"]) for o in obs) / n
    f, lo95, hi95 = wilson(k, n, Z95)
    _, loG, hiG = wilson(k, n, Z_GATE)
    ys = [o["y"] for o in obs]
    eo = collections.Counter(o["event"] for o in obs)
    dy = collections.Counter(o["day"] for o in obs)
    elo, ehi, edeff, _ = wilson_cluster(ys, [o["event"] for o in obs], Z_GATE)
    dlo, dhi, ddeff, _ = wilson_cluster(ys, [o["day"] for o in obs], Z_GATE)
    c.update({"k": k, "f": f, "w95": [lo95, hi95], "wG": [loG, hiG], "mean_px": mp, "mean_fee": mf,
              "events": len(eo), "days": len(dy), "max_event_share": max(eo.values()) / n, "max_day_share": max(dy.values()) / n,
              "nz_vol_share": sum(1 for o in obs if o["vol"] > 0) / n, "vol_upper_bound": sum(o["vol"] for o in obs),
              "w_event": [elo, ehi], "deff_event": edeff, "w_day": [dlo, dhi], "deff_day": ddeff})
    px = mp / 100.0
    fee = mf / 100.0
    if direction == "buy":
        c["edge_c"] = 100 * f - mp - mf
        c["clears_fee_gate"] = loG > px + fee
        c["clears_fee_event"] = elo > px + fee
        c["clears_fee_day"] = dlo > px + fee
    else:
        c["edge_c"] = mp - mf - 100 * f
        c["clears_fee_gate"] = hiG < px - fee
        c["clears_fee_event"] = ehi < px - fee
        c["clears_fee_day"] = dhi < px - fee
    c["interval_contains_price"] = bool(loG <= px <= hiG)
    # fee-band reading (descriptive only, NOT the frozen KILL rule): no fee-clearing edge in either direction
    c["no_fee_clearing_edge"] = not (c["clears_fee_gate"])
    c["event_adj_contains_price"] = bool(elo <= px <= ehi)
    c["floor_ok"] = bool(n >= 1000 and len(eo) >= 100 and len(dy) >= 20)
    c["g3_untrad_ok"] = bool(untrad_frac is not None and untrad_frac <= 0.70)
    c["g3_untrad_ok_strict"] = bool(strict_untrad is not None and strict_untrad <= 0.70)
    c["g4_vol_ok"] = bool(c["nz_vol_share"] >= 0.5)
    c["g5_conc_ok"] = bool(c["max_event_share"] <= 0.05 and c["max_day_share"] <= 0.25)
    c["pass_all"] = bool(c["clears_fee_gate"] and c["floor_ok"] and c["g3_untrad_ok"] and c["g4_vol_ok"] and c["g5_conc_ok"])
    return c


# ---------------------------------------------------------------------------------------------------- anchors (static)
def _names(node):
    s = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            s.add(n.id)
        elif isinstance(n, ast.arg):
            s.add(n.arg)
        elif isinstance(n, ast.Attribute):
            s.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"[A-Za-z_]\w{0,20}", n.value):
            s.add(n.value)                    # dict keys such as entry["ask"]; prose strings are not identifiers
    return s


def _is_ask(nm):
    return {x.lower() for x in nm if "ask" in x.lower() or x.lower() in ("ya", "_ya")}


def _is_bid(nm):
    return {x.lower() for x in nm if "bid" in x.lower() or x.lower() in ("yb", "_yb")}


PRICING_PATH_FUNCS = ["candle_rows", "entry_sides", "exec_price", "price_event", "bucket_of", "fee_c"]
NO_RESULT_FUNCS = PRICING_PATH_FUNCS + ["fetch_event", "paged"]


def scan_source(src, funcs_no_result=NO_RESULT_FUNCS, funcs_path=PRICING_PATH_FUNCS):
    """Raises AssertionError on: (c) any `100 - <ask>` (or `1 - <ask>`), any mid computation (an arithmetic expression
    combining a bid-ish and an ask-ish name, or a mid-ish identifier); (d) `result`/`results`/RESULT_KEY referenced
    inside any function that sits on the entry path."""
    tree = ast.parse(src)
    ev = {"n_100_minus_expr": 0, "n_binops_scanned": 0}
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp):
            ev["n_binops_scanned"] += 1
            nm = _names(n)
            if isinstance(n.op, ast.Sub) and isinstance(n.left, ast.Constant) and n.left.value in (100, 100.0, 1, 1.0):
                ev["n_100_minus_expr"] += 1
                assert not _is_ask(_names(n.right)), f"(c) 100-ask expression at line {n.lineno}"
            assert not (_is_ask(nm) and _is_bid(nm)), f"(c) bid and ask combined in one expression (mid / spread) at line {n.lineno}"
        if isinstance(n, (ast.Name, ast.arg)):
            ident = (n.id if isinstance(n, ast.Name) else n.arg).lower()
            assert not (ident == "mid" or ident.startswith("mid_") or ident.endswith("_mid") or "midpoint" in ident or "midprice" in ident), \
                f"(c) mid-ish identifier {ident!r} at line {n.lineno}"
    fdefs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for f in funcs_no_result:
        nm = _names(fdefs[f])
        assert not ({"result", "results", "RESULT_KEY"} & nm), f"(d) `result` referenced in entry-path function {f}"
    return ev


def anchor_static_checks():
    src = open(os.path.abspath(__file__)).read()
    ev = scan_source(src)
    ev["pricing_path_funcs"] = PRICING_PATH_FUNCS
    ev["no_result_funcs"] = NO_RESULT_FUNCS
    # NEGATIVE CONTROLS on doctored copies: each must raise
    controls = {}
    doctored = {
        "d_result_in_entry_sides": src.replace('    cutoff = close_ts - T * 60\n    if open_ts is not None',
                                               '    cutoff = close_ts - T * 60\n    _leak = raw.get("result")\n    if open_ts is not None', 1),
        "d_RESULT_KEY_in_price_event": src.replace('    out = []\n    for m in ladder:\n        raw = candles.get(m["ticker"])',
                                                   '    out = []\n    _leak = RESULT_KEY\n    for m in ladder:\n        raw = candles.get(m["ticker"])', 1),
        "c_100_minus_ask": src.replace('    if direction == "buy":\n        return entry["ask"]',
                                       '    if direction == "buy":\n        return 100 - entry["ask"]', 1),
        "c_mid_price": src.replace('    if direction == "sell":\n        return entry["bid"]',
                                   '    if direction == "sell":\n        return (entry["bid"] + entry["ask"]) / 2', 1),
    }
    for name, dsrc in doctored.items():
        assert dsrc != src, f"doctoring failed for {name}"
        try:
            scan_source(dsrc)
            controls[name] = "DID NOT RAISE"
        except AssertionError as e:
            controls[name] = "raised: " + str(e)[:90]
    assert all(v.startswith("raised") for v in controls.values()), controls
    ev["negative_controls"] = controls
    return ev


# ---------------------------------------------------------------------------------------------------- hand-worked observations (anchor c)
def hand_worked(rows, n=10):
    """First n priced T=15 observations PER DIRECTION in rr work order (rule fixed before outcomes), re-parsed from the raw
    candle JSON with code independent of normalize()."""
    out = {"buy": [], "sell": []}
    for r in rows:
        if r["T"] != 15 or r["why"] != "ok" or r["stream"] == "ANCHOR":
            continue
        for dname, key, raw_key in (("buy", "ask", "yes_ask"), ("sell", "bid", "yes_bid")):
            if len(out[dname]) >= n or r[key] is None or bucket_of(r[key]) is None:
                continue
            raw = jload(os.path.join(EVDIR, r["event"], "candles.json"))[r["ticker"]]
            cutoff = r["close_ts"] - 15 * 60
            cand = [c for c in raw if r["cts"] - 0 <= c["end_period_ts"] <= cutoff]
            c = max(cand, key=lambda c: c["end_period_ts"])
            node = c[raw_key]
            val = node.get("close_dollars", node.get("close"))
            px = int(round(float(val) * 100))
            assert px == r[key], (r["ticker"], px, r[key])
            assert c["end_period_ts"] == r["cts"]
            out[dname].append({"ticker": r["ticker"], "cutoff_ts": cutoff, "candle_end_ts": c["end_period_ts"],
                               "raw_field": raw_key, "raw_close": val, "price_used_c": px, "fee_c": fee_c(px),
                               "result": "yes" if r["y"] else "no", "executes_at": "yes_ask" if dname == "buy" else "yes_bid"})
        if all(len(v) >= n for v in out.values()):
            break
    return out


# ---------------------------------------------------------------------------------------------------- anchor (a1): replication from the cached TAIL_PRICING hours
TP_PUBLISHED_T15 = {   # out/tail_pricing.md, section 1, T = 15 (n priced, YES) -- transcribed before running
    "1": (400, 2), "2": (175, 2), "3": (149, 4), "4-5": (158, 6), "6-10": (234, 12), "11-20": (250, 39), "21-40": (322, 88)}


def cmd_replicate():
    """Run THIS module's pricing code (entry_sides with TAIL_PRICING's lookback) over the 503 cached TAIL_PRICING hours,
    sell direction at the bid, TAIL_PRICING's buckets, T=15; compare to the published table."""
    hours = sorted(h for h in os.listdir(TP_HOURS) if os.path.exists(os.path.join(TP_HOURS, h, "DONE")))
    tot = collections.Counter()
    obs = collections.defaultdict(list)
    n_all = n_untr = 0
    for h in hours:
        d = os.path.join(TP_HOURS, h)
        ladder, candles, res = jload(d + "/ladder.json"), jload(d + "/candles.json"), jload(d + "/results.json")
        for m in ladder:
            if not m["ticker"].rsplit("-", 1)[-1].startswith("T") or m.get("strike_type") not in ("greater", None):
                tot["excluded_non_T"] += 1
                continue
            e = entry_sides(candles.get(m["ticker"]), m["close_ts"], m.get("open_ts"), 15, floor_ts=m["close_ts"] - 80 * 60)
            r = res.get(m["ticker"])
            if r not in ("yes", "no"):
                tot["no_result"] += 1
                continue
            n_all += 1
            px = exec_price(e, "sell")
            if px is None:
                n_untr += 1
                continue
            obs[bucket_of(px, TP_BUCKETS + [("41-60", 41, 60), ("61-80", 61, 80), ("81-100", 81, 100)])].append(
                {"price": px, "y": 1 if r == "yes" else 0, "event": h, "day": TP.utc_day(m["close_ts"]), "vol": e["vol"]})
    rows, ok_all = [], True
    for name, lo, hi in TP_BUCKETS:
        o = obs.get(name, [])
        k = sum(x["y"] for x in o)
        pub = TP_PUBLISHED_T15[name]
        match = (len(o), k) == pub
        ok_all &= match
        f, wl, wh = wilson(k, len(o), Z95)
        mb = sum(x["price"] for x in o) / len(o) if o else None
        rows.append({"bucket": name, "n": len(o), "k": k, "published_n": pub[0], "published_k": pub[1], "exact_match": match,
                     "f": f, "w95": [wl, wh], "mean_bid": mb, "bid_inside_w95": bool(wl * 100 <= mb <= wh * 100) if o else None})
    res = {"hours": len(hours), "strike_T_obs": n_all, "untradeable_bid": n_untr, "untradeable_frac": n_untr / n_all if n_all else None,
           "published_untradeable_frac_T15": 0.466, "rows": rows, "all_7_buckets_exact": ok_all, "other": dict(tot)}
    jdump(res, os.path.join(CACHE, "replicate_a1.json"))
    print(json.dumps(res, indent=1)[:3000])
    return res


# ---------------------------------------------------------------------------------------------------- verify (official result re-read via single GET)
def cmd_verify(n=40):
    done = [e for s, e in jload(os.path.join(CACHE, "rr_order.json")) if os.path.exists(os.path.join(EVDIR, e, "DONE"))]
    done += [e for e in jload(os.path.join(CACHE, "streams.json"))["ANCHOR"] if os.path.exists(os.path.join(EVDIR, e, "DONE"))]
    rng = random.Random(SEED + 1)
    pool = []
    for e in rng.sample(done, min(len(done), 300)):
        pool += [(e, x["ticker"]) for x in jload(os.path.join(EVDIR, e, "markets.json"))]
    out, mism = [], 0
    for e, tk in rng.sample(pool, min(n, len(pool))):
        mine = jload(os.path.join(EVDIR, e, "results.json")).get(tk)
        try:
            m = http(f"/markets/{tk}")["market"]
        except Exception:
            m = http(f"/historical/markets/{tk}")["market"]
        ok = (m.get("result") == mine)
        mism += (not ok)
        out.append({"ticker": tk, "listing_result": mine, "single_get_result": m.get("result"), "match": ok})
    jdump({"n": len(out), "mismatches": mism, "rows": out}, os.path.join(CACHE, "verify_d.json"))
    print("verified", len(out), "mismatches", mism)


# ---------------------------------------------------------------------------------------------------- analyze
def stream_coverage():
    streams = jload(os.path.join(CACHE, "streams.json"))
    cov = {}
    for s in STREAMS:
        lst = streams[s]
        isdone = [os.path.exists(os.path.join(EVDIR, e, "DONE")) for e in lst]
        pre = 0
        for x in isdone:
            if x:
                pre += 1
            else:
                break
        nd = sum(isdone)
        cov[s] = {"universe_events": len(lst), "done_events": nd, "fraction": nd / len(lst) if lst else None,
                  "exact_prefix_len": pre, "is_exact_prefix": pre == nd}
    return cov


def build_obs_table(rows):
    """rows -> {(scope, T, dir, bucket): [obs]} plus per-(scope,T,dir) counters.  ANCHOR rows are Crypto (KXBTCD is a Crypto
    series): they count in scope 'Crypto' and in scope 'ANCHOR'.  `den`/`untr` exclude not-yet-open markets (primary);
    `den_s`/`untr_s` keep them as untradeable (strict reading)."""
    cells = collections.defaultdict(list)
    den, untr, den_s, untr_s, outside = (collections.Counter() for _ in range(5))
    for r in rows:
        for scope in ((r["cat"], "ANCHOR") if r["stream"] == "ANCHOR" else (r["cat"],)):
            for d in DIRS:
                k = (scope, r["T"], d)
                den_s[k] += 1
                if r["why"] == "not_open":
                    untr_s[k] += 1
                    continue
                den[k] += 1
                px = exec_price(r, d)
                if px is None:
                    untr[k] += 1
                    untr_s[k] += 1
                    continue
                b = bucket_of(px)
                if b is None:
                    outside[k] += 1
                    continue
                cells[(scope, r["T"], d, b)].append({"price": px, "y": r["y"], "event": r["event"], "day": r["day"], "vol": r["vol"],
                                                     "two": r["bid"] is not None and r["ask"] is not None})
    return cells, den, untr, den_s, untr_s, outside


def pooled_stats(obs, direction):
    """DESCRIPTIVE, outside the frozen 280-cell family, never gated: calibration-in-the-large over all 10 buckets of one
    (category, T, direction).  gap = mean(100*y - executable price) in cents; net = the fee-inclusive per-contract edge of
    the taker in this direction (buy: 100y - ask - fee, sell: bid - fee - 100y), with an event-cluster-robust (CR1) SE."""
    n = len(obs)
    if n < 2:
        return {"n": n}
    gap = [100.0 * o["y"] - o["price"] for o in obs]
    sign = 1.0 if direction == "buy" else -1.0
    net = [sign * g - fee_c(o["price"]) for g, o in zip(gap, obs)]
    out = {"n": n, "events": len({o["event"] for o in obs})}
    for name, xs in (("gap", gap), ("net", net)):
        m = sum(xs) / n
        cl = collections.defaultdict(float)
        for x, o in zip(xs, obs):
            cl[o["event"]] += x - m
        G = len(cl)
        se = math.sqrt((G / (G - 1.0)) * sum(u * u for u in cl.values())) / n if G > 1 else None
        out[name] = {"mean_c": m, "se_c": se, "ci95": [m - 1.96 * se, m + 1.96 * se] if se is not None else None}
    return out


def cmd_analyze():
    chk = anchor_static_checks()
    cov = stream_coverage()
    streams = jload(os.path.join(CACHE, "streams.json"))
    meta = jload(os.path.join(CACHE, "event_meta.json"))
    rr = jload(os.path.join(CACHE, "rr_order.json"))
    seq = [("ANCHOR", e) for e in streams["ANCHOR"]] + [(s, e) for s, e in rr]
    seq = [(s, e) for s, e in seq if os.path.exists(os.path.join(EVDIR, e, "DONE"))]
    # ---- PRICING PASS: no result loaded ----
    entries, parts, ev_parts = [], collections.Counter(), {}
    n_markets = collections.Counter()
    fetch_none = collections.Counter()
    for s, e in seq:
        es = price_event(e)
        for x in es:
            x["stream"], x["cat"] = s, meta[e]["c"]
        entries += es
        dn = jload(os.path.join(EVDIR, e, "DONE"))
        parts[dn["part"]] += 1
        n_markets[s] += dn["n"]
        ev_parts[e] = dn["part"]
    for x in entries:
        if x.get("fetch_none") and x["why"] != "not_open":
            fetch_none[(x["stream"], x["T"])] += 1
    # ---- first moment results are read ----
    results = {e: jload(os.path.join(EVDIR, e, "results.json")) for s, e in seq}
    rows, excl_join = join_results(entries, results)
    cells, den, untr, den_s, untr_s, outside = build_obs_table(rows)
    hand = hand_worked(rows)

    # exclusions / counts
    notopen = collections.Counter((r["stream"], r["T"]) for r in rows if r["why"] == "not_open")
    why_ct = collections.Counter((r["stream"], r["T"], r["why"]) for r in rows)
    side_missing = collections.Counter()
    for r in rows:
        if r["why"] == "ok":
            if r["bid"] is None:
                side_missing[(r["cat"], r["T"], "bid_absent")] += 1
            if r["ask"] is None:
                side_missing[(r["cat"], r["T"], "ask_absent_or_100")] += 1
    stale = collections.defaultdict(list)
    for r in rows:
        if r["why"] == "ok":
            stale[(r["cat"], r["T"])].append(r["stale"])
    stale_sum = {f"{k[0]}|{k[1]}": {"n": len(v), "median_s": sorted(v)[len(v) // 2], "p90_s": sorted(v)[int(len(v) * 0.9)]}
                 for k, v in stale.items() if v}

    # partition sanity (e)
    by_ev = collections.defaultdict(list)
    for s, e in seq:
        for tk, r in results[e].items():
            by_ev[e].append(r)
    part_fail, part_stats = [], collections.Counter()
    for e, rs in by_ev.items():
        if meta[e]["me"] is not True:
            part_stats["not_mutually_exclusive_event"] += 1
            continue
        if not all(r in ("yes", "no") for r in rs):
            part_stats["me_event_with_non_yes_no_result"] += 1
            part_fail.append({"event": e, "cat": meta[e]["c"], "n_markets": len(rs), "yes": sum(r == "yes" for r in rs),
                              "issue": "non_yes_no_result_present", "results": dict(collections.Counter(rs))})
            continue
        ny = sum(r == "yes" for r in rs)
        if ny == 1:
            part_stats["me_event_exactly_one_yes"] += 1
        else:
            part_stats["me_event_not_exactly_one_yes"] += 1
            part_fail.append({"event": e, "cat": meta[e]["c"], "n_markets": len(rs), "yes": ny, "issue": f"{ny}_yes"})

    # ---- cells ----
    out_cells = {}
    scopes = CATS + ["ANCHOR"]
    for sc in scopes:
        for T in TS:
            for d in DIRS:
                k3 = (sc, T, d)
                U = untr[k3] / den[k3] if den[k3] else None
                Us = untr_s[k3] / den_s[k3] if den_s[k3] else None
                for name, lo, hi in BUCKETS:
                    c = cell_stats(cells.get((sc, T, d, name), []), U, d, Us)
                    out_cells[f"{sc}|{T}|{d}|{name}"] = dict(c, scope=sc, T=T, dir=d, bucket=name)

    pooled, pooled_two = {}, {}
    for sc in scopes:
        for T in TS:
            for d in DIRS:
                allobs = [o for name, _, _ in BUCKETS for o in cells.get((sc, T, d, name), [])]
                pooled[f"{sc}|{T}|{d}"] = pooled_stats(allobs, d)
                pooled_two[f"{sc}|{T}|{d}"] = pooled_stats([o for o in allobs if o["two"]], d)
    ev_in_scope = {sc: (cov[sc]["done_events"] + (cov["ANCHOR"]["done_events"] if sc == "Crypto" else 0)) if sc != "ANCHOR" else cov["ANCHOR"]["done_events"] for sc in scopes}
    throughput_ev_per_h = None
    try:
        lg = open(os.path.join(CACHE, "fetch_rr.log")).read().strip().splitlines()[-1]
        mm = re.search(r"fetched (\d+) fails \d+ in (\d+)s", lg)
        throughput_ev_per_h = int(mm.group(1)) / int(mm.group(2)) * 3600
    except Exception:
        pass
    power = {}
    for sc in CATS:
        need = []
        for T in TS:
            for d in DIRS:
                for name, _, _ in BUCKETS:
                    nn = len(cells.get((sc, T, d, name), []))
                    if nn:
                        need.append(max(1000.0 * ev_in_scope[sc] / nn, 100.0))
        need.sort()
        power[sc] = {"events_priced": ev_in_scope[sc], "cells_populated": len(need),
                     "cells_n_ge_1000_now": sum(1 for T in TS for d in DIRS for name, _, _ in BUCKETS if len(cells.get((sc, T, d, name), [])) >= 1000),
                     "events_needed_p25": need[len(need) // 4] if need else None, "events_needed_median": need[len(need) // 2] if need else None,
                     "events_needed_p75": need[3 * len(need) // 4] if need else None,
                     "events_in_universe": cov[sc]["universe_events"] if sc != "Crypto" else cov["Crypto"]["universe_events"] + cov["ANCHOR"]["universe_events"]}
    power["_throughput_events_per_hour_all_streams"] = throughput_ev_per_h

    # ---- verdict (frozen rule, verbatim) ----
    fam = {k: c for k, c in out_cells.items() if c["scope"] in CATS}
    passing = [k for k, c in fam.items() if c.get("pass_all")]
    floor_cells = [k for k, c in fam.items() if c.get("floor_ok")]
    kill = bool(floor_cells) and all(fam[k]["interval_contains_price"] for k in floor_cells)
    verdict = "PASS" if passing else ("KILL" if kill else "INSUFFICIENT")
    # descriptive (NOT frozen): among floor cells, how many have a fee-clearing edge on the literal interval; and event-adjusted
    desc = {"floor_cells": len(floor_cells), "floor_cells_interval_excludes_price": sum(1 for k in floor_cells if not fam[k]["interval_contains_price"]),
            "floor_cells_clearing_fee_literal": sum(1 for k in floor_cells if fam[k]["clears_fee_gate"]),
            "floor_cells_clearing_fee_event_adj": sum(1 for k in floor_cells if fam[k]["clears_fee_event"]),
            "floor_cells_clearing_fee_day_adj": sum(1 for k in floor_cells if fam[k]["clears_fee_day"]),
            "cells_with_any_n": sum(1 for c in fam.values() if c["n"]),
            "cells_clearing_fee_literal_any_n": [k for k, c in fam.items() if c.get("clears_fee_gate")],
            "cells_clearing_fee_event_adj_any_n": [k for k, c in fam.items() if c.get("clears_fee_event")]}

    # ---- anchor (a2): fresh KXBTCD stratum ----
    a2_cells = {k: c for k, c in out_cells.items() if c["scope"] == "ANCHOR"}
    a2_long = [c for c in a2_cells.values() if c["dir"] == "sell" and c["bucket"] in LONGSHOT and c["n"] >= 30]
    a2_in = sum(1 for c in a2_long if c["w95"][0] * 100 <= c["mean_px"] <= c["w95"][1] * 100)
    a2_in_G = sum(1 for c in a2_long if c["interval_contains_price"])
    a2_frac = a2_in / len(a2_long) if a2_long else None
    # TAIL_PRICING-bucket table on the fresh stratum, sell direction, T=15 (same buckets as published table)
    a2_tp = []
    obs_tp = collections.defaultdict(list)
    for r in rows:
        if r["stream"] == "ANCHOR" and r["T"] == 15 and r["why"] == "ok":
            px = exec_price(r, "sell")
            if px is not None:
                b = bucket_of(px, TP_BUCKETS)
                if b:
                    obs_tp[b].append({"price": px, "y": r["y"]})
    for name, lo, hi in TP_BUCKETS:
        o = obs_tp.get(name, [])
        k = sum(x["y"] for x in o)
        f, wl, wh = wilson(k, len(o), Z95)
        mb = sum(x["price"] for x in o) / len(o) if o else None
        a2_tp.append({"bucket": name, "n": len(o), "k": k, "f": f, "w95": [wl, wh], "mean_bid": mb,
                      "inside": bool(wl * 100 <= mb <= wh * 100) if o else None})
    a1 = jload(os.path.join(CACHE, "replicate_a1.json")) if os.path.exists(os.path.join(CACHE, "replicate_a1.json")) else None
    a2_pass = bool(a2_frac is not None and a2_frac >= 0.8)
    anchor_a = {"a1": a1, "a2_long_cells": len(a2_long), "a2_inside_w95": a2_in, "a2_inside_wGate": a2_in_G, "a2_fraction_inside_w95": a2_frac,
                "a2_pass": a2_pass, "a2_tp_bucket_table_T15": a2_tp,
                "a1_pass": bool(a1 and a1["all_7_buckets_exact"]), "anchor_a_pass": bool(a1 and a1["all_7_buckets_exact"] and a2_pass)}

    vp = os.path.join(CACHE, "verify_d.json")
    rep = {"spec": "CATALOG_CALIBRATION_SPEC.md", "seed": SEED, "verdict": verdict, "n_comparisons": N_COMP, "alpha": ALPHA, "z_gate": Z_GATE,
           "coverage": cov, "events_by_partition": dict(parts), "markets_by_stream": dict(n_markets),
           "universe_summary": jload(os.path.join(CACHE, "universe_summary.json")),
           "exclusions": {"join": dict(excl_join), "not_open_by_stream_T": {f"{k[0]}|{k[1]}": v for k, v in notopen.items()},
                          "fetch_gap_none_candles_by_stream_T": {f"{k[0]}|{k[1]}": v for k, v in fetch_none.items()},
                          "outside_bucket_priced_99_by_scope_T_dir": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in outside.items()},
                          "side_missing_priced_candle": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in side_missing.items()},
                          "why_by_stream_T": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in why_ct.items()}},
           "staleness": stale_sum, "partition": {"stats": dict(part_stats), "failures": part_fail},
           "cells": out_cells, "pooled_descriptive": pooled, "pooled_two_sided_descriptive": pooled_two, "power": power, "family_pass_cells": passing, "family_floor_cells": floor_cells, "descriptive": desc,
           "anchors": {"a": anchor_a, "c_d_static": chk, "hand_worked_10_per_direction": hand,
                       "d_verify": jload(vp) if os.path.exists(vp) else None},
           "counts": {"entries_priced_pass": len(entries), "rows_with_official_result": len(rows)}}
    pr = os.path.join(CACHE, "plain_reading.md")
    rep["plain_reading"] = open(pr).read() if os.path.exists(pr) else None
    jdump(rep, OUT_JSON)
    write_md(rep)
    print("verdict", verdict, "| anchor a pass", anchor_a["anchor_a_pass"], "| floor cells", len(floor_cells), "| pass cells", len(passing))
    return rep


# ---------------------------------------------------------------------------------------------------- report
def pct(x, nd=2):
    return "n/a" if x is None else f"{x * 100:.{nd}f}%"


def num(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def write_md(rep):
    L = []
    C = rep["cells"]
    cov = rep["coverage"]
    A = rep["anchors"]["a"]
    L.append("# Catalog calibration: is the executable price ever off the realised frequency by more than the fee?\n")
    L.append(f"**VERDICT: {rep['verdict']}** (frozen PASS/KILL rule applied verbatim; section 8)   |   **Anchor (a) replication control: "
             f"{'REPLICATED' if A['anchor_a_pass'] else 'DID NOT REPLICATE -- PIPELINE NOT TRUSTED'}**\n")
    L.append(f"Spec CATALOG_CALIBRATION_SPEC.md, registered 2026-10-29. {rep['n_comparisons']} comparisons; Bonferroni two-sided alpha = {rep['alpha']:.3e}; "
             f"gate z = {rep['z_gate']:.4f} (99.982% Wilson). Seed {rep['seed']}.\n")
    plain = os.path.join(CACHE, "plain_reading.md")
    if os.path.exists(plain):
        L.append(open(plain).read())
    L.append("## 0b. One-line-per-category summary\n")
    L.append("| category | events priced | priced cells (of 40) | floor cells (crit. 2) | literal 99.982% interval clears price+fee | event-adjusted clears | literal interval contains price (of populated) | cells with f above buy-ask+fee or below sell-bid-fee by point estimate |")
    L.append("|---|--:|--:|--:|--:|--:|--:|--:|")
    for sc in CATS:
        cs = [c for k, c in C.items() if c["scope"] == sc]
        pop = [c for c in cs if c["n"]]
        L.append(f"| {sc} | {cov[sc]['done_events'] + (cov['ANCHOR']['done_events'] if sc == 'Crypto' else 0):,} | {len(pop)} | {sum(1 for c in pop if c['floor_ok'])} | {sum(1 for c in pop if c['clears_fee_gate'])} | "
                 f"{sum(1 for c in pop if c['clears_fee_event'])} | {sum(1 for c in pop if c['interval_contains_price'])} | {sum(1 for c in pop if c['edge_c'] > 0)} |")
    L.append("")
    # ---------------- 1. anchor (a)
    L.append("## 1. Anchor (a): crypto replication control (KXBTCD), reported first\n")
    a1 = A["a1"]
    if a1:
        L.append(f"**(a1) Exact re-derivation.** This module's pricing code (`entry_sides`, `exec_price`, `bucket_of`) run over the {a1['hours']} cached TAIL_PRICING hours, sell at the executable bid, T=15, TAIL_PRICING's longshot buckets. "
                 f"Untradeable (no bid) fraction {pct(a1['untradeable_frac'], 1)} vs published 46.6%. **All 7 buckets reproduce TAIL_PRICING's published n and YES count exactly: {'YES' if a1['all_7_buckets_exact'] else 'NO'}.**\n")
        L.append("| bucket (bid) | n (mine) | YES (mine) | n (published) | YES (published) | exact | realised rate | Wilson 95% | mean bid | bid inside 95% CI |")
        L.append("|---|--:|--:|--:|--:|:--:|--:|---|--:|:--:|")
        for r in a1["rows"]:
            L.append(f"| {r['bucket']}c | {r['n']} | {r['k']} | {r['published_n']} | {r['published_k']} | {'yes' if r['exact_match'] else 'NO'} | {pct(r['f'])} | "
                     f"[{pct(r['w95'][0])}, {pct(r['w95'][1])}] | {num(r['mean_bid'])}c | {'yes' if r['bid_inside_w95'] else 'NO'} |")
    L.append("")
    L.append(f"**(a2) Fresh KXBTCD stratum, full pipeline (new fetch + new pricing).** {cov['ANCHOR']['done_events']} of {cov['ANCHOR']['universe_events']} KXBTCD hourly events "
             f"({pct(cov['ANCHOR']['fraction'], 1)}; exact prefix of the saved shuffle: {cov['ANCHOR']['is_exact_prefix']}). "
             f"Sell-direction longshot cells (frozen buckets <= 40c, T in {{15, 60}}, n >= 30): **{A['a2_inside_w95']} of {A['a2_long_cells']}** have the mean executable bid inside the 95% Wilson interval "
             f"({pct(A['a2_fraction_inside_w95'], 1)}; bar >= 80%; TAIL_PRICING: 27 of 28). With the 99.982% interval: {A['a2_inside_wGate']} of {A['a2_long_cells']}.\n")
    L.append("TAIL_PRICING-bucket table on the fresh stratum, T=15, sell at bid:\n")
    L.append("| bucket (bid) | n | YES | realised | Wilson 95% | mean bid | inside |")
    L.append("|---|--:|--:|--:|---|--:|:--:|")
    for r in A["a2_tp_bucket_table_T15"]:
        L.append(f"| {r['bucket']}c | {r['n']} | {r['k']} | {pct(r['f'])} | [{pct(r['w95'][0])}, {pct(r['w95'][1])}] | {num(r['mean_bid'])}c | {'yes' if r['inside'] else ('NO' if r['inside'] is not None else 'n/a')} |")
    L.append("")
    # ---------------- 2. coverage
    L.append("## 2. Sampling and coverage\n")
    L.append("Whole events, one stream per category (KXBTCD is its own ANCHOR stream, removed from Crypto so the two are disjoint), each stream sorted by ticker then shuffled once with `random.Random(20261029)` and saved (`cache/catalog_calib/streams.json`, `rr_order.json`); never re-sorted. Categories processed round-robin in the saved order.\n")
    L.append("| stream | events in universe | events priced | covered fraction | exact prefix of saved order | prefix length | markets listed |")
    L.append("|---|--:|--:|--:|:--:|--:|--:|")
    for s in STREAMS:
        c = cov[s]
        L.append(f"| {s} | {c['universe_events']:,} | {c['done_events']:,} | {pct(c['fraction'], 2)} | {'yes' if c['is_exact_prefix'] else 'NO'} | {c['exact_prefix_len']:,} | {rep['markets_by_stream'].get(s, 0):,} |")
    L.append(f"\nEvents served by the live API vs `/historical`: {rep['events_by_partition']}.\n")
    # ---------------- 3. calibration curves
    L.append("## 3. Anchor (b): calibration curves (the deliverable, whatever the verdict)\n")
    L.append("Per category x direction x T x frozen bucket. `f` = realised YES frequency (official `result`). `px` = mean executable price (ask for buy, bid for sell, cents). "
             "`edge` = cents per contract before sizing: buy `100f - ask - fee`, sell `bid - fee - 100f` (descriptive; there is no EV t-gate). `W99.98` = the gate's Wilson interval; `evt-adj` = same interval widened by the event design effect. "
             "`gate` = per-bar flags `P` (fee-clearing on the literal interval) / `N` (n>=1000, >=100 events, >=20 days) / `U` (untradeable <= 70%) / `V` (>=50% nonzero entry volume) / `C` (no event >5%, no day >25%). `vol<=` = summed entry-candle volume, an upper bound only.\n")
    for sc in CATS + ["ANCHOR"]:
        title = sc if sc != "ANCHOR" else "ANCHOR stratum: KXBTCD (subset of Crypto; reported separately, not part of the 280)"
        L.append(f"\n### {title}\n")
        for T in TS:
            for d in DIRS:
                cs = [C[f"{sc}|{T}|{d}|{b[0]}"] for b in BUCKETS]
                u = cs[0]["untradeable_frac"]
                L.append(f"\n**{sc}, T={T}, {'BUY YES at ask' if d == 'buy' else 'SELL YES at bid'}** (untradeable {pct(u, 1)}; strict incl. not-yet-open {pct(cs[0]['untradeable_frac_strict'], 1)})\n")
                L.append("| bucket | n | events | days | YES | f | W95 | W99.98 | evt-adj | px | fee | edge c | nz-vol | vol<= | gate P/N/U/V/C |")
                L.append("|---|--:|--:|--:|--:|--:|---|---|---|--:|--:|--:|--:|--:|:--:|")
                for (name, _, _), c in zip(BUCKETS, cs):
                    if not c["n"]:
                        L.append(f"| {name} | 0 | | | | | | | | | | | | | |")
                        continue
                    g = "".join(ch if ok else "-" for ch, ok in zip("PNUVC", [c["clears_fee_gate"], c["floor_ok"], c["g3_untrad_ok"], c["g4_vol_ok"], c["g5_conc_ok"]]))
                    L.append(f"| {name} | {c['n']:,} | {c['events']:,} | {c['days']} | {c['k']:,} | {pct(c['f'])} | [{pct(c['w95'][0])}, {pct(c['w95'][1])}] | "
                             f"[{pct(c['wG'][0])}, {pct(c['wG'][1])}] | [{pct(c['w_event'][0])}, {pct(c['w_event'][1])}] | {num(c['mean_px'])} | {num(c['mean_fee'], 2)} | "
                             f"{c['edge_c']:+.2f} | {pct(c['nz_vol_share'], 0)} | {c['vol_upper_bound']:,.0f} | {g} |")
    # ---------------- 4. gate table
    L.append("\n## 4. Per-cell gate table (the 280 comparisons)\n")
    L.append("Only cells with any priced observation are listed; empty cells (n = 0) can satisfy nothing. Columns: gate 1 = Wilson bound clears price+fee on the literal interval; 1e/1d = same on the event-/day-adjusted interval; "
             "2 = n>=1000 & >=100 events & >=20 days; 3 = untradeable <= 70% (primary; strict reading in brackets); 4 = >=50% nonzero volume; 5 = no event >5%, no day >25%; contains = literal 99.982% interval contains the mean executable price.\n")
    L.append("| category | T | dir | bucket | n | events | days | f | px | g1 | g1e | g1d | g2 | g3 | g4 | g5 | contains px | PASS |")
    L.append("|---|--:|---|---|--:|--:|--:|--:|--:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|")
    yn = lambda b: "Y" if b else "n"
    for sc in CATS:
        for T in TS:
            for d in DIRS:
                for name, _, _ in BUCKETS:
                    c = C[f"{sc}|{T}|{d}|{name}"]
                    if not c["n"]:
                        continue
                    L.append(f"| {sc} | {T} | {d} | {name} | {c['n']:,} | {c['events']:,} | {c['days']} | {pct(c['f'])} | {num(c['mean_px'])} | {yn(c['clears_fee_gate'])} | {yn(c['clears_fee_event'])} | {yn(c['clears_fee_day'])} | "
                             f"{yn(c['floor_ok'])} | {yn(c['g3_untrad_ok'])}[{yn(c['g3_untrad_ok_strict'])}] | {yn(c['g4_vol_ok'])} | {yn(c['g5_conc_ok'])} | {yn(c['interval_contains_price'])} | {yn(c['pass_all'])} |")
    L.append(f"\nCells in the family with at least one priced observation: {rep['descriptive']['cells_with_any_n']} of {rep['n_comparisons']}.\n")
    # ---------------- 5. anchors c d e f
    ad = rep["anchors"]
    L.append("## 5. Anchors (c), (d), (e), (f)\n")
    L.append("### (c) Executable sides only\n")
    s = ad["c_d_static"]
    L.append(f"AST scan of this whole module: {s['n_binops_scanned']} binary expressions scanned, {s['n_100_minus_expr']} of the form `100 - x` / `1 - x`, none with an ask-ish name on the right; no expression combines a bid-ish and an ask-ish name (so no mid, no spread); no mid-ish identifier. "
             "Buy price is read only through `exec_price(entry, 'buy') -> entry['ask']`, sell only through `... 'sell' -> entry['bid']`.\n")
    L.append("Negative controls on doctored copies of this file (each must raise):\n")
    for k, v in s["negative_controls"].items():
        L.append(f"* `{k}`: {v}")
    L.append("\nHand-worked observations re-parsed from the RAW candle JSON (independent of `normalize()`; asserted equal to the price used):\n")
    for dname in DIRS:
        L.append(f"\n{dname.upper()} -- executes at {'yes_ask' if dname == 'buy' else 'yes_bid'}:\n")
        L.append("| ticker | candle end | cutoff | raw field | raw close | price used (c) | fee (c) | official result |")
        L.append("|---|--:|--:|---|--:|--:|--:|---|")
        for h in ad["hand_worked_10_per_direction"][dname]:
            L.append(f"| {h['ticker']} | {h['candle_end_ts']} | {h['cutoff_ts']} | {h['raw_field']} | {h['raw_close']} | {h['price_used_c']} | {h['fee_c']} | {h['result']} |")
    L.append("\n### (d) No outcome in the entry path\n")
    L.append(f"`result` is read in `split_listing` (fetch side: moves it into `results.json`), in `join_results` (analysis), and by the `replicate` / `verify` commands. AST-asserted absent from {s['no_result_funcs']}. "
             "The pricing pass over all events completed before `results.json` was opened for any of them. Negative controls above (`d_*`) raised on doctored copies.\n")
    v = ad["d_verify"]
    if v:
        L.append(f"Official-result provenance: {v['n']} random markets re-read through `GET /markets/{{ticker}}` (or `/historical/markets/{{ticker}}`): **{v['mismatches']} mismatches**.\n")
    P = rep["partition"]
    L.append("### (e) Partition sanity\n")
    L.append(f"Events checked, by kind: {P['stats']}. A `mutually_exclusive` event is expected to resolve exactly one YES when every market has a yes/no result. Failures: **{len(P['failures'])}**.\n")
    if P["failures"]:
        L.append("| event | category | markets | YES count | issue |")
        L.append("|---|---|--:|--:|---|")
        for f in P["failures"][:60]:
            L.append(f"| {f['event']} | {f['cat']} | {f['n_markets']} | {f['yes']} | {f['issue']} |")
        if len(P["failures"]) > 60:
            L.append(f"\n... {len(P['failures']) - 60} more in the JSON.")
    L.append("\n### (f) Size is not measured\n")
    L.append("Candles carry no depth. `vol<=` is the summed volume of the ENTRY candle only (contracts traded in that one minute): an upper bound on what printed in that minute, and nothing more. Realisable size at the quoted price is unknown. "
             "`yes_bid_size_fp` / `yes_ask_size_fp` exist on OPEN markets only, so this gap cannot be backfilled for settled markets.\n")
    # ---------------- 6. exclusions
    X = rep["exclusions"]
    L.append("## 6. Exclusions, with counts and reasons\n")
    U = rep["universe_summary"]
    L.append(f"* Event walk: {U['events_walked']:,} settled events listed by `/events?status=settled`; by category: {U['by_category_all']}. In scope: the 7 spec categories only. Out of scope (not in the frozen 7): Elections, Entertainment, Mentions, Science and Technology, Companies, Social, World, etc. -- note Elections is a separate catalog category from Politics.")
    L.append(f"* Multivariate (KXMVE*) events in scope categories excluded from the universe: {U['excluded_mve_in_scope_categories']:,}.")
    L.append(f"* Not yet trading at the entry cutoff (open_time >= close - T, so no candle can end at or before it): excluded as non-observations, counted per stream|T: {X['not_open_by_stream_T']}. The strict reading (kept in the denominator as untradeable) is reported as the bracketed gate-3 value.")
    L.append(f"* Markets without an official yes/no `result` (voided, scalar, empty), counted per candle-entry: {X['join']}.")
    L.append(f"* Candle fetch returned nothing for the ticker (API gap; treated as no candle, kept in denominator): {X['fetch_gap_none_candles_by_stream_T']}.")
    L.append(f"* Priced but outside every frozen bucket (executable price 99c; ask 100 is counted untradeable), per scope|T|dir: {X['outside_bucket_priced_99_by_scope_T_dir']}.")
    L.append(f"* Priced-candle entries missing the relevant side, per category|T|side: {X['side_missing_priced_candle']}.")
    L.append("* Untradeable entries (no candle within 120 min before the cutoff, or the relevant side absent) are kept in every denominator and never priced or back-filled.")
    L.append("* Staleness of the entry candle (seconds before the cutoff), priced candles: " + "; ".join(f"{k}: median {v['median_s']}s, p90 {v['p90_s']}s" for k, v in rep["staleness"].items()) + "\n")
    # ---------------- 7 diagnostics
    D = rep["descriptive"]
    L.append("## 7. Descriptive summary of the 280 comparisons (not a gate)\n")
    L.append(f"* Cells with any priced observation: {D['cells_with_any_n']}. Cells meeting the criterion-2 n floor (n>=1000, >=100 events, >=20 days): **{D['floor_cells']}**.")
    L.append(f"* Of the floor cells, the literal 99.982% interval excludes the executable price in **{D['floor_cells_interval_excludes_price']}** and clears price+fee (profitable direction) in **{D['floor_cells_clearing_fee_literal']}** "
             f"(event-adjusted: {D['floor_cells_clearing_fee_event_adj']}; day-adjusted: {D['floor_cells_clearing_fee_day_adj']}).")
    L.append(f"* Cells (any n) whose literal interval clears price+fee: {D['cells_clearing_fee_literal_any_n'] or 'none'}. Event-adjusted: {D['cells_clearing_fee_event_adj_any_n'] or 'none'}.")
    L.append("\n### 7b. Pooled calibration-in-the-large (DESCRIPTIVE; outside the frozen 280; no verdict uses it)\n")
    L.append("All 10 buckets pooled per category x T x direction. `gap` = mean(100*y - executable price) in cents (positive: YES happens more often than the price implies). "
             "`net` = the taker's fee-inclusive edge per contract in that direction. Event-cluster-robust 95% CI. This is the resolution of the whole experiment: a pooled mispricing smaller than the CI half-width could not have been seen.\n")
    L.append("| category | T | direction | n | events | gap (c) | 95% CI | net edge after fee (c) | 95% CI |")
    L.append("|---|--:|---|--:|--:|--:|---|--:|---|")
    for sc in CATS + ["ANCHOR"]:
        for T in TS:
            for d in DIRS:
                q = rep["pooled_descriptive"][f"{sc}|{T}|{d}"]
                if q.get("n", 0) < 2:
                    continue
                g, nt = q["gap"], q["net"]
                L.append(f"| {sc} | {T} | {d} | {q['n']:,} | {q['events']:,} | {g['mean_c']:+.2f} | [{g['ci95'][0]:+.2f}, {g['ci95'][1]:+.2f}] | {nt['mean_c']:+.2f} | [{nt['ci95'][0]:+.2f}, {nt['ci95'][1]:+.2f}] |")
    L.append("\n**7b-ii. Same, restricted to entries where BOTH sides were quoted on the entry candle** (robustness diagnostic for one-sided stale books; a restriction of the SAME frozen observations by a flag known before the outcome, not a new cell search; no verdict uses it).\n")
    L.append("| category | T | direction | n | events | gap (c) | 95% CI | net edge after fee (c) | 95% CI |")
    L.append("|---|--:|---|--:|--:|--:|---|--:|---|")
    for sc in CATS + ["ANCHOR"]:
        for T in TS:
            for d in DIRS:
                q = rep["pooled_two_sided_descriptive"][f"{sc}|{T}|{d}"]
                if q.get("n", 0) < 2 or q["gap"]["ci95"] is None:
                    continue
                g, nt = q["gap"], q["net"]
                L.append(f"| {sc} | {T} | {d} | {q['n']:,} | {q['events']:,} | {g['mean_c']:+.2f} | [{g['ci95'][0]:+.2f}, {g['ci95'][1]:+.2f}] | {nt['mean_c']:+.2f} | [{nt['ci95'][0]:+.2f}, {nt['ci95'][1]:+.2f}] |")
    L.append("\n### 7c. Power: how far the sample is from the criterion-2 floor\n")
    P2 = rep["power"]
    tp = P2.get("_throughput_events_per_hour_all_streams")
    L.append(f"Linear extrapolation of events needed for a cell to reach n>=1000 (and >=100 events), from its current density. Measured fetch throughput over the round-robin run: {tp:.0f} events/hour across all 7 streams (API-limited, HTTP 429 on ~1 call in 4).\n" if tp else "")
    L.append("| category | events priced | events in universe | populated cells | cells with n>=1000 now | events needed: densest quartile cell | median cell | sparsest quartile cell |")
    L.append("|---|--:|--:|--:|--:|--:|--:|--:|")
    for sc in CATS:
        q = P2[sc]
        f0 = lambda x: "n/a" if x is None else f"{x:,.0f}"
        L.append(f"| {sc} | {q['events_priced']:,} | {q['events_in_universe']:,} | {q['cells_populated']} | {q['cells_n_ge_1000_now']} | {f0(q['events_needed_p25'])} | {f0(q['events_needed_median'])} | {f0(q['events_needed_p75'])} |")
    # ---------------- 8 verdict
    L.append("\n## 8. Verdict: frozen rule applied verbatim, numbers beside each bar\n")
    L.append(f"* PASS requires, in at least one category x bucket x direction x T cell, ALL of: (1) Wilson 99.982% bound clears price+fee; (2) n>=1000 priced across >=100 events and >=20 days; (3) untradeable <= 70%; (4) >=50% nonzero entry volume; (5) no event >5%, no day >25%. "
             f"Cells passing all five: **{len(rep['family_pass_cells'])}** ({', '.join(rep['family_pass_cells']) or 'none'}).")
    L.append(f"* KILL requires, in EVERY cell meeting criterion 2, the 99.982% Wilson interval to contain the executable price in both directions. Floor cells: **{D['floor_cells']}**; of which the interval contains the price: "
             f"**{D['floor_cells'] - D['floor_cells_interval_excludes_price']}**.")
    L.append(f"* Result: **{rep['verdict']}**.\n")
    open(OUT_MD, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    args = sys.argv[2:]
    if c == "universe":
        cmd_universe()
    elif c == "fetch":
        mx = int(args[args.index("--max-events") + 1]) if "--max-events" in args else None
        bs = float(args[args.index("--budget-s") + 1]) if "--budget-s" in args else None
        cmd_fetch(args[0], mx, bs)
    elif c == "replicate":
        cmd_replicate()
    elif c == "verify":
        cmd_verify()
    elif c == "analyze":
        cmd_analyze()
