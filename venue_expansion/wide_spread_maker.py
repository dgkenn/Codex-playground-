"""wide_spread_maker.py -- executes WIDE_SPREAD_MAKER_SPEC.md (registered 2026-10-29).  Nothing here may move a bar.

QUESTION. Both earlier maker studies ran on KXBTCD (tightest book on the venue).  On the wide-spread products the spread is
revenue for a maker (9,029 of 9,191 series are taker-only fee).  Is there a SWEET SPOT: enough flow to fill, enough spread
to pay, adverse selection not consuming the difference?  Anchor (f) (flow vs spread, jointly) is the deliverable.

STAGES (every stage resumable, cached under cache/wide_maker/, sequential, User-Agent, exponential backoff):
  universe   series x events from the READ-ONLY catalog_calib event walk; per-series frozen shuffle (seed 20261029); saved.
  list       one /markets?series_ticker page per series: criterion 1a (>= 50 settled markets with official yes/no result)
             and the lifetime-volume share L+ (a rigorous upper bound on every flow statistic, see ENTRY-VOLUME BOUND).
  screen     candles for the frozen shuffled events of each series that survives 1a and L+ >= 0.5, until >= SCREEN_N covered
             markets; criteria 1 (candle coverage), 2 (median spread >= 5c at T=15, both sides quoted), 3 (median entry-candle
             volume > 0).  Writes selection.json.  NO outcome is read by this stage except the yes/no COUNT of criterion 1.
  place      quotes for the passers (candles only; no tape, no result) -> quotes.json with sha256.
  tape       GET /markets/trades for exactly the quoted tickers with lifetime volume > 0 (validated fetcher in maker_fill).
  raw        re-pull RAW tape JSON for 10 fills per side (hand-worked anchor c).
  analyze    anchors, cells, gates, verdict -> out/wide_spread_maker.{json,md}.

FROZEN INTERPRETATION CHOICES (spec silent or ambiguous; fixed BEFORE any fill or outcome was computed):
  * Universe: series of the seven categories (Sports, Politics, Financials, Economics, Climate and Weather, Commodities,
    Elections) that have >= 1 non-MVE event in the LIVE partition (last_updated >= 2026-08-29, the catalog_calibration walk,
    cache/catalog_calib/events_all.jsonl, read only).  Events migrated to /historical (served at ~1 call per market) are out
    of reach and are counted, not hidden.  Crypto is excluded by the spec.  KXMVE multivariate products are excluded.
  * Criterion 1: >= 50 settled markets with official result in {yes, no} (listing) AND >= 50 of the screened markets carry an
    entry candle at T=15.  Criterion 2: median(yes_ask - yes_bid) >= 5c over markets whose T=15 entry candle has BOTH sides
    quoted (bid in 1..99, ask in 1..99; an empty ask prints as 100c and is NOT a quote).  Criterion 3: median entry-candle
    volume_fp > 0 over ALL markets with a T=15 entry candle (the spec phrases C3 without the both-sides qualifier; the
    both-sided variant is reported beside it).  Median = numpy median (mean of the middle two for even n); a series whose
    median is positive ONLY through that averaging (exactly half zeros) is flagged.
  * Entry candle = last candle with end_period_ts <= close - T*60 and >= close - T*60 - 120min (a quote 'exists' only if
    seen within two hours).  Market not yet open at the cutoff = not an observation (excluded, counted).
  * ENTRY-VOLUME BOUND.  The entry candle's volume is <= the market's lifetime volume.  If fewer than half the series'
    settled markets ever traded (L+ < 0.5), median entry volume is 0 for the whole series, so C3 fails without a single
    candle.  Such series are 'excluded by criterion 3 (implied by lifetime volume)'.  Criterion 2 is NOT evaluated for them
    (no candle fetched) and is said so.  Same bound: a quote can only fill if a print occurs, so fill rate <= L+.
  * Screening sample: frozen shuffled events, whole events, until SCREEN_N covered markets (or events exhausted / cap).
    The study continues down the SAME saved order.  Series that hit the event cap with < SCREEN_N covered are reported as
    UNRESOLVED_CAP, not as criterion failures.
  * Quotes: per market x T in {15, 60} x k in {1, 2}: sell YES at a = yes_bid + k and buy YES at d = yes_ask - k, both
    sides quoted at the entry candle.  One contract each.  No re-quote, no cancel.  Live t0 < t <= close.  Quotes are NOT
    filtered by spread width (spec silent): a = bid+k >= ask rests behind the best ask and is counted and labelled
    ('at_or_behind' diagnostic); a strictly-inside split is reported as information only.
  * Fill, on the tape.  RESTING SELL at a fills on a taker BUY (taker_side == "yes") at yes_price >= a.  RESTING BUY at d
    fills on a taker SELL (taker_side == "no") at yes_price <= d.  Cumulative qualifying count_fp in (t0, close]:
    optimistic V > 0; pessimistic V > N (strict) for N in {25, 100}.
  * Bonferroni family = passing series x 2 k x 2 T x 2 sides x 2 fill models (optimistic and N=25; N=100 is disclosed as
    sensitivity outside the family, as in MAKER_FILL/FAVOURITE_MAKER).  Wilson bounds at z = Phi^-1(1 - 0.05/M/2).
  * 'Cell meeting the n floor' (KILL) = under N=25: n_filled >= 500, >= 100 distinct events, >= 20 distinct UTC days.
  * Calendar day = UTC date of close.  Official `result` only.

Usage:  python wide_spread_maker.py universe | list | screen | selection | place | tape | raw | analyze
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tail_pricing as TP                  # wilson, cluster_stats, utc_day, iso2ts, _adapt (reused, not rebuilt)
import edge_sizing_v2 as V2                # normalize(): the shared candle parser
import maker_fill as MF                    # VALIDATED tape fetcher (fetch_ticker, iso_us) -- reused
from scipy import stats as st
import numpy as np

V2.WINDOW_MIN = 600
API = "https://api.elections.kalshi.com/trade-api/v2"
UA = "wide-spread-maker-research/1.0"
CACHE = os.environ.get("WSM_CACHE") or os.path.join(HERE, "cache", "wide_maker")      # WSM_CACHE: scratch dry-run only
CC_CACHE = os.path.join(HERE, "cache", "catalog_calib")          # READ ONLY
CC_EVDIR = os.path.join(CC_CACHE, "events")                       # READ ONLY
SS_MARKETS = os.path.join(HERE, "cache", "shape_screen", "series_markets")      # READ ONLY (monotone count shortcut)
LISTING = os.path.join(CACHE, "listing")                  # markets (no result)
LISTING_RES = os.path.join(CACHE, "listing_results")       # official results, a SEPARATE file read only by the join step
EVDIR = os.path.join(CACHE, "events")
TAPE = os.path.join(CACHE, "tape")
UNIVERSE = os.path.join(CACHE, "universe.json")
SCREEN = os.path.join(CACHE, "screen.json")
SELECTION = os.path.join(CACHE, "selection.json")
QUOTES = os.path.join(CACHE, "quotes.json")
HAND_RAW = os.path.join(CACHE, "hand_raw10.json")
OUT_JSON = (os.environ["WSM_CACHE"] + "/dry.json") if os.environ.get("WSM_CACHE") else os.path.join(HERE, "out", "wide_spread_maker.json")
OUT_MD = (os.environ["WSM_CACHE"] + "/dry.md") if os.environ.get("WSM_CACHE") else os.path.join(HERE, "out", "wide_spread_maker.md")

SEED = 20261029
LIVE_CUT = "2026-08-29T00:00:00Z"
CATS = ["Sports", "Politics", "Financials", "Economics", "Climate and Weather", "Commodities", "Elections"]
TS = (15, 60)
KS = (1, 2)
SIDES = ("sell", "buy")
MODELS = ("opt", "n25", "n100")
FAMILY_MODELS = ("opt", "n25")
MODEL_LABEL = {"opt": "optimistic (front of queue)", "n25": "pessimistic N=25", "n100": "pessimistic N=100"}
STALE_CAP_MIN = 120
FETCH_BACK_MIN = 60 + STALE_CAP_MIN + 1
CHUNK = 40
SCREEN_N = 50                       # covered markets needed (criterion 1 threshold); medians are taken over the screened markets
EVENT_CAP = 40                      # screening cap in events per series
SPREAD_BAR = 5
NOCOV_EVENTS = 10                   # stop a series after this many events if fewer than 3 markets have an entry candle (no coverage to screen)
EARLY_N = 15                        # sequential C2 stop: need this many both-sided observations ...
EARLY_Z = 2.576                     # ... and the one-sided 99.5% Wilson UPPER bound of share(spread >= 5c) below one half
L_PLUS_BAR = 0.25
BOOT_SEED = 20261029
BOOT_B = 2000
FILL_TAKER_SIDE = {"sell": "y", "buy": "n"}          # resting SELL <- taker BUY ('yes'); resting BUY <- taker SELL ('no')
RESULT_KEY = "result"

_last = [0.0]
PACE = [0.7]
STATS = {"calls": 0, "r429": 0, "other": 0}


# ------------------------------------------------------------------------------------- io + http
def jload(p, default=None):
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return default


def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(o, fh)
    os.replace(tmp, p)


def get(path, tries=10):
    """Sequential, paced, User-Agent, exponential backoff on 429/5xx; 400/404 raise at once."""
    for i in range(tries):
        wait = PACE[0] - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as fh:
                out = json.load(fh)
            STATS["calls"] += 1
            PACE[0] = max(0.5, PACE[0] - 0.05)
            return out
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                raise
            STATS["r429" if e.code == 429 else "other"] += 1
            PACE[0] = min(1.2, PACE[0] + 0.1)
            time.sleep(min(60, 1.0 * 2 ** i))
        except Exception:
            STATS["other"] += 1
            time.sleep(min(60, 1.0 * 2 ** i))
    raise RuntimeError("giving up: " + path)


MF._get = lambda path, tries=14, gap=0.22: get(path)      # the validated tape fetcher, run through THIS module's pacing


def utc_day(ts):
    return TP.utc_day(ts)


# ------------------------------------------------------------------------------------- universe
def cmd_universe():
    """Series universe + per-series frozen shuffle.  Deterministic: sorted base order, random.Random(f'{SEED}:{series}')."""
    seen, ev = set(), []
    for line in open(os.path.join(CC_CACHE, "events_all.jsonl")):
        d = json.loads(line)
        if d["e"] in seen:
            continue
        seen.add(d["e"])
        ev.append(d)
    live = [d for d in ev if (d.get("lu") or "") >= LIVE_CUT]
    hist = [d for d in ev if (d.get("lu") or "") < LIVE_CUT]
    keep = [d for d in live if d["c"] in CATS and not d["e"].startswith("KXMVE")]
    mve = [d for d in live if d["c"] in CATS and d["e"].startswith("KXMVE")]
    by = collections.defaultdict(list)
    cat_of = {}
    for d in keep:
        by[d["s"]].append(d["e"])
        cat_of[d["s"]] = d["c"]
    series = {}
    for s in sorted(by):
        evs = sorted(set(by[s]))
        random.Random(f"{SEED}:{s}").shuffle(evs)                 # ONE seeded shuffle per series; saved; never re-sorted
        series[s] = {"cat": cat_of[s], "events": evs}
    hist_cat = collections.Counter(d["c"] for d in hist if d["c"] in CATS)
    jdump({"seed": SEED, "live_cut": LIVE_CUT, "series": series,
           "events_walked_total": len(ev), "events_live": len(live), "events_historical_band_excluded": len(hist),
           "historical_band_in_scope_categories": dict(hist_cat), "mve_excluded": len(mve)}, UNIVERSE)
    c = collections.Counter(v["cat"] for v in series.values())
    print("series", len(series), dict(c), "events", sum(len(v["events"]) for v in series.values()), flush=True)


# ------------------------------------------------------------------------------------- listing (criterion 1a, L+)
def split_listing(markets):
    """The ONLY place in the listing path that reads the official `result` key; it keeps COUNTS and a separate result map."""
    slim, res = [], {}
    for m in markets:
        tk = m["ticker"]
        slim.append({"ticker": tk, "event": m.get("event_ticker"),
                     "close_ts": TP.iso2ts(m["close_time"]) if m.get("close_time") else None,
                     "open_ts": TP.iso2ts(m["open_time"]) if m.get("open_time") else None,
                     "vol_life": float(m.get("volume_fp") or 0), "strike_type": m.get("strike_type")})
        res[tk] = m.get(RESULT_KEY)
    return slim, res


def cmd_list():
    uni = jload(UNIVERSE)
    os.makedirs(LISTING, exist_ok=True)
    todo = [s for s in uni["series"] if not os.path.exists(os.path.join(LISTING, s + ".json"))]
    print("series to list", len(todo), flush=True)
    t0 = time.time()
    for i, s in enumerate(todo, 1):
        # monotone shortcut: a series that already had >= 50 yes/no settled markets in shape_screen's Oct-27 pull still has them
        # (the count of settled markets with a result only grows), but we still need L+ and the market list -> fresh pull anyway.
        mk, cur, pages = [], "", 0
        while True:
            try:
                r = get(f"/markets?series_ticker={s}&status=settled&limit=1000&mve_filter=exclude" + (f"&cursor={cur}" if cur else ""))
            except Exception as e:
                print("FAIL", s, str(e)[:80], flush=True)
                mk = None
                break
            mk += r.get("markets", [])
            pages += 1
            cur = r.get("cursor")
            if not cur or pages >= 1:                       # ONE page (<= 1000 markets): far past every threshold; truncation is flagged and disclosed
                break
        if mk is None:
            continue
        slim, res = split_listing(mk)
        n_yn = sum(1 for v in res.values() if v in ("yes", "no"))
        jdump(res, os.path.join(LISTING_RES, s + ".json"))
        jdump({"series": s, "pages": pages, "truncated": bool(cur), "n_returned": len(mk), "n_yes_no": n_yn,
               "markets": slim}, os.path.join(LISTING, s + ".json"))
        if i % 20 == 0:
            print(f"listed {i}/{len(todo)}  {time.time() - t0:.0f}s  {STATS}  pace={PACE[0]:.2f}", flush=True)
    print("list done", STATS, flush=True)




# ------------------------------------------------------------------------------------- entry candle (SCREEN + PLACEMENT PATH)
# Everything between here and `class_end` reads candles at or before the cutoff ONLY.  It must not see a result, the tape,
# a fill or any outcome (anchor d), must not compute `100 - ask` and must not compute a mid price (anchor e).  AST-scanned.
def candle_rows(raw, close_ts):
    """-> sorted [(ts, yes_bid_c, yes_ask_c, vol)] via the shared edge_sizing_v2.normalize()."""
    if not raw:
        return []
    return sorted(V2.normalize(TP._adapt(raw), close_ts), key=lambda r: r[0])


def side_present(px):
    """A side is quoted iff its printed price is strictly inside (0, 100).  An EMPTY ask prints as 100c, an empty bid as 0."""
    return px is not None and 0 < px < 100


def entry_obs(raw, close_ts, open_ts, T):
    """THE entry rule: last candle with cutoff-120min <= end_period_ts <= close - T*60.  No look-around, no back-fill."""
    cutoff = close_ts - T * 60
    if open_ts is not None and open_ts >= cutoff:
        return {"why": "not_open", "bid": None, "ask": None, "vol": 0.0, "stale": None}
    floor_ts = cutoff - STALE_CAP_MIN * 60
    pick = None
    for ts, yes_bid, yes_ask, vol in candle_rows(raw, close_ts):
        if floor_ts <= ts <= cutoff:
            pick = (ts, yes_bid, yes_ask, vol)
    if pick is None:
        return {"why": "no_candle", "bid": None, "ask": None, "vol": 0.0, "stale": None}
    ts, yes_bid, yes_ask, vol = pick
    return {"why": "ok", "bid": int(yes_bid) if side_present(yes_bid) else None,
            "ask": int(yes_ask) if side_present(yes_ask) else None, "vol": float(vol), "stale": cutoff - ts}


def spread_c(bid, ask):
    """yes_ask - yes_bid in cents: the criterion-2 statistic.  The ONLY function permitted to combine the two sides."""
    return ask - bid


def both_sided(o):
    """Both sides quoted AND not crossed/locked (a crossed candle is a stale print, not a book)."""
    return o["why"] == "ok" and o["bid"] is not None and o["ask"] is not None and o["bid"] < o["ask"]


def make_quotes(o, T, k):
    """Quotes for one entry observation.  Sell at bid + k, buy at ask - k, each requiring both sides quoted (void otherwise).
    Returns (sell_px, buy_px, why)."""
    if o["why"] != "ok":
        return None, None, o["why"]
    if o["bid"] is None or o["ask"] is None:
        return None, None, "one_side_absent"
    if not both_sided(o):
        return None, None, "crossed_or_locked"
    a = o["bid"] + k
    d = o["ask"] - k
    if not (1 <= a <= 99 and 1 <= d <= 99):
        return None, None, "price_out_of_range"
    return a, d, "ok"


def place_event(event, ladder, candles):
    """Candles only.  ladder: [{ticker, close_ts, open_ts, vol_life}].  Returns (quotes, exclusion counter)."""
    qs, ex = [], collections.Counter()
    for m in ladder:
        raw = candles.get(m["ticker"])
        for T in TS:
            o = entry_obs(raw, m["close_ts"], m["open_ts"], T)
            for k in KS:
                a, d, why = make_quotes(o, T, k)
                if why != "ok":
                    ex[(T, k, why)] += 1
                    continue
                qs.append({"event": event, "ticker": m["ticker"], "close_ts": m["close_ts"], "day": utc_day(m["close_ts"]),
                           "T": T, "k": k, "bid": o["bid"], "ask": o["ask"], "a": a, "d": d, "stale": o["stale"],
                           "evol": o["vol"], "vol_life": m["vol_life"]})
    return qs, ex


PLACEMENT_FUNCS = ["candle_rows", "side_present", "entry_obs", "spread_c", "both_sided", "make_quotes", "place_event"]
FORBIDDEN_IN_PLACEMENT = {"result", "results", "RESULT_KEY", "tape", "TAPE", "trades", "fill", "fills", "fill_times",
                          "load_tape", "res", "taker_side", "count_fp", "yes", "y", "listing_results", "LISTING_RES"}
MIX_ALLOWED_IN = {"spread_c"}                 # the only function that may put a bid-ish and an ask-ish name in one expression
# class_end


# ------------------------------------------------------------------------------------- event store (fetch + cache)
def split_event_listing(markets):
    slim, res = split_listing(markets)
    ladder = [x for x in slim if x["close_ts"]]
    return ladder, {x["ticker"]: res[x["ticker"]] for x in ladder}


def get_listing(s):
    return jload(os.path.join(LISTING, s + ".json"))


def event_markets_api(e):
    mk, cur = [], ""
    while True:
        r = get(f"/markets?event_ticker={e}&limit=1000" + (f"&cursor={cur}" if cur else ""))
        mk += r.get("markets", [])
        cur = r.get("cursor")
        if not cur:
            return mk


def fetch_candles(ladder):
    candles = {}
    groups = collections.defaultdict(list)
    for x in ladder:
        groups[x["close_ts"]].append(x["ticker"])
    for close_ts, tks in groups.items():
        for i in range(0, len(tks), CHUNK):
            chunk = tks[i:i + CHUNK]
            r = get("/markets/candlesticks?market_tickers=" + ",".join(chunk) +
                    f"&start_ts={close_ts - FETCH_BACK_MIN * 60}&end_ts={close_ts - min(TS) * 60}&period_interval=1")
            got = {m.get("market_ticker") or m.get("ticker"): m.get("candlesticks") for m in r.get("markets", [])}
            for t in chunk:
                candles[t] = got.get(t)
    return candles


def ensure_event(e, s):
    """Make cache/wide_maker/events/<e>/{markets,candles,results}.json + DONE exist.  Returns a status string.
    Priority: own cache -> READ-ONLY copy from the catalog_calib cache (same window, same endpoint) -> API."""
    d = os.path.join(EVDIR, e)
    if os.path.exists(os.path.join(d, "DONE")):
        return "cached"
    cc = os.path.join(CC_EVDIR, e)
    if os.path.exists(os.path.join(cc, "DONE")):
        dn = jload(os.path.join(cc, "DONE"))
        mk = jload(os.path.join(cc, "markets.json"))
        if dn.get("part") != "live":
            jdump([], os.path.join(d, "markets.json"))
            jdump({}, os.path.join(d, "candles.json"))
            jdump({}, os.path.join(d, "results.json"))
            jdump({"part": "hist_skipped", "n": len(mk), "t": int(time.time())}, os.path.join(d, "DONE"))
            return "hist_skipped"
        ladder = [{"ticker": x["ticker"], "event": e, "close_ts": x["close_ts"], "open_ts": x["open_ts"],
                   "vol_life": float(x.get("vol_final") or 0), "strike_type": x.get("strike_type")} for x in mk if x["close_ts"]]
        jdump(ladder, os.path.join(d, "markets.json"))
        jdump(jload(os.path.join(cc, "candles.json")), os.path.join(d, "candles.json"))
        jdump(jload(os.path.join(cc, "results.json")), os.path.join(d, "results.json"))
        jdump({"part": "live", "n": len(ladder), "src": "catalog_calib", "t": int(time.time())}, os.path.join(d, "DONE"))
        return "from_catalog_cache"
    lst = get_listing(s)
    if lst is not None and not lst["truncated"]:
        ladder = [dict(m) for m in lst["markets"] if m["event"] == e and m["close_ts"]]
        allres = jload(os.path.join(LISTING_RES, s + ".json"), {})
        res = {m["ticker"]: allres.get(m["ticker"]) for m in ladder}
        src = "series_listing"
    else:
        ladder, res = split_event_listing(event_markets_api(e))
        for m in ladder:
            m["event"] = e
        src = "event_api"
    candles = fetch_candles(ladder) if ladder else {}
    jdump(ladder, os.path.join(d, "markets.json"))
    jdump(res, os.path.join(d, "results.json"))
    jdump(candles, os.path.join(d, "candles.json"))
    jdump({"part": "live" if ladder else "empty", "n": len(ladder), "src": src, "t": int(time.time())}, os.path.join(d, "DONE"))
    return "fetched"


def load_event(e):
    d = os.path.join(EVDIR, e)
    return jload(os.path.join(d, "markets.json")), jload(os.path.join(d, "candles.json"))


def load_results(e):
    return jload(os.path.join(EVDIR, e, "results.json"))


# ------------------------------------------------------------------------------------- listing statistics (criterion 1a, L+)
def listing_stats(s):
    """Counts only.  Reads the SEPARATE results file solely to count markets with an official yes/no result."""
    lst = get_listing(s)
    if lst is None:
        return None
    res = jload(os.path.join(LISTING_RES, s + ".json"), {})
    yn = [m for m in lst["markets"] if res.get(m["ticker"]) in ("yes", "no")]
    vols = [m["vol_life"] for m in yn]
    trad = sum(1 for v in vols if v > 0)
    return {"n_returned": lst["n_returned"], "truncated": lst["truncated"], "n_yes_no": len(yn),
            "n_traded_life": trad, "L_plus": trad / len(yn) if yn else None,
            "median_life_vol": float(np.median(vols)) if vols else None,
            "mean_life_vol": float(np.mean(vols)) if vols else None, "events_in_listing": len({m["event"] for m in lst["markets"]})}


def screen_candidates(uni):
    """Series that must be screened with candles: C1a holds and the lifetime-volume bound does not already decide C3."""
    out, ex = [], collections.Counter()
    for s in uni["series"]:
        ls = listing_stats(s)
        if ls is None:
            ex["not_listed_yet"] += 1
            continue
        if ls["n_yes_no"] < 50:
            ex["c1a_lt50_results"] += 1
        elif ls["L_plus"] < L_PLUS_BAR:
            ex["c3_implied_by_lifetime_volume"] += 1
        else:
            out.append(s)
    return out, ex


# ------------------------------------------------------------------------------------- screening (criteria 1, 2, 3)
def event_screen_counts(e):
    """T=15 entry statistics of one event's markets with an official yes/no result.  The result is used ONLY as a filter."""
    ladder, candles = load_event(e)
    ok_res = {t for t, v in load_results(e).items() if v in ("yes", "no")}
    c = collections.Counter()
    spreads, vols, vols_two = [], [], []
    for m in ladder:
        if m["ticker"] not in ok_res:
            c["no_official_yes_no_result"] += 1
            continue
        o = entry_obs(candles.get(m["ticker"]), m["close_ts"], m["open_ts"], 15)
        c["markets"] += 1
        if o["why"] != "ok":
            c[o["why"]] += 1
            continue
        c["covered"] += 1
        vols.append(o["vol"])
        if o["bid"] is None:
            c["bid_absent"] += 1
        if o["ask"] is None:
            c["ask_absent_or_100"] += 1
        if both_sided(o):
            c["both_sided"] += 1
            spreads.append(spread_c(o["bid"], o["ask"]))
            vols_two.append(o["vol"])
    return c, spreads, vols, vols_two


def cmd_screen():
    uni = jload(UNIVERSE)
    cands, ex = screen_candidates(uni)
    pri = ["Elections", "Politics", "Financials", "Economics", "Climate and Weather", "Commodities", "Sports"]
    cands.sort(key=lambda s: (pri.index(uni["series"][s]["cat"]), s))          # processing ORDER only; every candidate is screened
    print("screen candidates", len(cands), dict(ex), flush=True)
    sdir = os.path.join(CACHE, "screen")
    os.makedirs(sdir, exist_ok=True)
    t0 = time.time()
    for i, s in enumerate(cands, 1):
        p = os.path.join(sdir, s + ".json")
        if os.path.exists(p) and jload(p).get("complete"):
            continue
        evs = uni["series"][s]["events"]
        tot, sp, vo, vt = collections.Counter(), [], [], []
        used, failed, stop = [], [], "exhausted"
        for j, e in enumerate(evs):
            if tot["covered"] >= SCREEN_N:
                stop = "enough"
                break
            if j >= EVENT_CAP:
                stop = "cap"
                break
            try:
                ensure_event(e, s)
            except Exception as ex_:
                failed.append(e)
                print("FAIL", s, e, str(ex_)[:60], flush=True)
                continue
            c, a, b, c2 = event_screen_counts(e)
            tot.update(c)
            sp += a
            vo += b
            vt += c2
            used.append(e)
            n_two = len(sp)
            if len(used) >= NOCOV_EVENTS and tot["covered"] < 3:
                stop = "no_coverage"
                break
            if n_two >= EARLY_N and TP.wilson(sum(1 for x in sp if x >= SPREAD_BAR), n_two, EARLY_Z)[2] < 0.5:
                stop = "early_C2"          # the median spread is below 5c with overwhelming confidence: stop paying for candles
                break
        jdump({"series": s, "complete": not failed, "events_used": used, "events_failed": failed, "stop": stop,
               "counts": dict(tot), "spreads": sp, "vols": vo, "vols_two": vt}, p)
        if i % 10 == 0:
            print(f"screened {i}/{len(cands)}  {time.time() - t0:.0f}s  {STATS}  pace={PACE[0]:.2f}", flush=True)
    print("screen done", STATS, flush=True)


def med(xs):
    return float(np.median(xs)) if len(xs) else None


def evaluate_series(s, uni):
    """One selection row.  Criteria evaluated in spec order; every failing criterion is listed."""
    ls = listing_stats(s)
    row = {"series": s, "cat": uni["series"][s]["cat"], "events_universe": len(uni["series"][s]["events"]), "listing": ls}
    if ls is None:
        row.update({"status": "NOT_LISTED", "failed": ["listing_missing"]})
        return row
    if ls["n_yes_no"] < 50:
        row.update({"status": "EXCLUDED", "failed": ["C1"], "reason": f"C1: only {ls['n_yes_no']} settled markets with an official yes/no result"})
        return row
    if ls["L_plus"] < L_PLUS_BAR:
        row.update({"status": "EXCLUDED", "failed": ["C3"],
                    "reason": f"C3 (implied): only {ls['L_plus'] * 100:.1f}% of settled markets ever traded, so median entry-candle volume is 0; C2 not evaluated"})
        return row
    sc = jload(os.path.join(CACHE, "screen", s + ".json"))
    if sc is None:
        row.update({"status": "NOT_SCREENED", "failed": ["screen_missing"]})
        return row
    cnt = sc["counts"]
    n_cov, n_two = cnt.get("covered", 0), cnt.get("both_sided", 0)
    ms, mv, mvt = med(sc["spreads"]), med(sc["vols"]), med(sc["vols_two"])
    row["screen"] = {"events_screened": len(sc["events_used"]), "stop": sc["stop"], "markets": cnt.get("markets", 0),
                     "covered": n_cov, "both_sided": n_two, "not_open": cnt.get("not_open", 0), "no_candle": cnt.get("no_candle", 0),
                     "bid_absent": cnt.get("bid_absent", 0), "ask_absent_or_100": cnt.get("ask_absent_or_100", 0),
                     "median_spread": ms, "median_entry_vol": mv, "median_entry_vol_two_sided": mvt,
                     "share_entry_vol_pos": (sum(1 for v in sc["vols"] if v > 0) / len(sc["vols"])) if sc["vols"] else None,
                     "boundary_median_vol": bool(sc["vols"] and mv is not None and mv > 0 and sum(1 for v in sc["vols"] if v == 0) * 2 == len(sc["vols"])),
                     "thin_two_sided": n_two < 10}
    failed = []
    if sc["stop"] == "early_C2":
        failed = ["C2"] + (["C3"] if not (mv is not None and mv > 0) else [])
        row.update({"status": "EXCLUDED", "failed": failed,
                    "reason": f"C2 (sequential stop after {len(sc['events_used'])} events): median both-sided spread {ms}c, "
                              f"{sum(1 for x in sc['spreads'] if x >= SPREAD_BAR)} of {n_two} both-sided entries >= {SPREAD_BAR}c "
                              f"(one-sided 99.5% Wilson upper bound of that share < 0.5); C1 coverage not completed"})
        return row
    if sc["stop"] == "no_coverage":
        row.update({"status": "EXCLUDED", "failed": ["C1"],
                    "reason": f"C1: only {n_cov} markets with an entry candle after {len(sc['events_used'])} events (no candle coverage); C2/C3 not evaluable"})
        return row
    if n_cov < SCREEN_N:
        if sc["stop"] == "cap":
            row.update({"status": "UNRESOLVED_CAP", "failed": ["C1_unresolved"],
                        "reason": f"event cap {EVENT_CAP} reached with {n_cov} < {SCREEN_N} covered markets"})
            return row
        failed.append("C1")
    if not (ms is not None and ms >= SPREAD_BAR):
        failed.append("C2")
    if not (mv is not None and mv > 0):
        failed.append("C3")
    row["failed"] = failed
    row["status"] = "PASS_SELECTION" if not failed else "EXCLUDED"
    if failed:
        row["reason"] = "; ".join({"C1": f"C1: only {n_cov} markets with an entry candle after exhausting all {len(sc['events_used'])} events",
                                   "C2": f"C2: median both-sided spread {ms if ms is not None else 'n/a'}c < {SPREAD_BAR}c (n={n_two})",
                                   "C3": f"C3: median entry-candle volume {mv if mv is not None else 'n/a'} not > 0"}[f] for f in failed)
    return row


def cmd_selection():
    uni = jload(UNIVERSE)
    rows = [evaluate_series(s, uni) for s in uni["series"]]
    passers = [r["series"] for r in rows if r["status"] == "PASS_SELECTION"]
    cands, ex = screen_candidates(uni)
    tally = collections.Counter()
    for r in rows:
        tally[(r["cat"], r["status"], tuple(r.get("failed", [])))] += 1
    jdump({"rows": rows, "passers": passers, "n_series": len(rows),
           "tally": {"|".join([a, b, "+".join(c)]): v for (a, b, c), v in tally.items()},
           "screened_candidates": len(cands), "prefilter": dict(ex),
           "params": {"SCREEN_N": SCREEN_N, "EVENT_CAP": EVENT_CAP, "SPREAD_BAR": SPREAD_BAR, "L_PLUS_BAR": L_PLUS_BAR}}, SELECTION)
    prim = passers
    supp = [r["series"] for r in rows if r.get("failed") == ["C3"] and "screen" in r]
    # The comparison count is fixed HERE, from the mechanical selection alone, before any quote, tape or outcome exists.
    jdump({"primary_series": prim, "M_primary": 16 * len(prim), "per_series": "2 k x 2 T x 2 sides x 2 fill models (opt, n25)",
           "supplement_series": supp, "M_supplement": 16 * len(supp), "frozen_at_epoch": int(time.time()),
           "frozen_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, os.path.join(CACHE, "comparisons.json"))
    print("series", len(rows), "passers", passers, "supplement", len(supp), "M_primary", 16 * len(prim))
    print(collections.Counter(r["status"] for r in rows))


# ------------------------------------------------------------------------------------- fills (tape)  [NOT on the placement path]
def qualifies(side_char, price, px, resting):
    """Does one print fill our resting order?
         resting SELL at px  <- a taker BUY  (taker_side 'yes'), at yes_price >= px
         resting BUY  at px  <- a taker SELL (taker_side 'no'),  at yes_price <= px
    Anything else (wrong taker side, or wrong side of our price) does NOT fill.  The two directions are NOT symmetric copies."""
    if resting == "sell":
        return side_char == FILL_TAKER_SIDE["sell"] and price >= px - 1e-9
    if resting == "buy":
        return side_char == FILL_TAKER_SIDE["buy"] and price <= px + 1e-9
    raise ValueError(resting)


def fill_times(rows, t0_us, close_us, px, resting):
    """rows sorted [(ts_us, yes_price_c, count, side_char)].  -> (opt, n25, n100) fill times in us, or None.
    V(t) = cumulative qualifying count_fp in (t0, close].  opt: V > 0.  pessimistic N: V > N (strict)."""
    cum, opt, f25, f100 = 0.0, None, None, None
    for ts, p, c, s in rows:
        if ts <= t0_us:
            continue
        if ts > close_us:
            break
        if not qualifies(s, p, px, resting):
            continue
        cum += c
        if opt is None:
            opt = ts
        if f25 is None and cum > 25:
            f25 = ts
        if f100 is None and cum > 100:
            f100 = ts
    return opt, f25, f100


def assert_side_maps():
    """Anchor (c), code half.  Both directions on synthetic prints; each direction must reject the other direction's prints."""
    sell_rows = [(1_000_001, 30.0, 30.0, "n"),     # taker SELL at/above our ask: hits a bid, NOT a fill of a resting ask
                 (1_000_002, 29.0, 30.0, "y"),     # taker BUY below our ask: lifts a cheaper offer, NOT a fill
                 (1_000_003, 30.0, 30.0, "y")]     # taker BUY at our ask: FILL
    o, f25, _ = fill_times(sell_rows, 1_000_000, 2_000_000, 30, "sell")
    assert o == 1_000_003 and f25 == 1_000_003, "resting SELL: only a taker BUY (yes) at yes_price >= a fills"
    assert fill_times(sell_rows[:2], 1_000_000, 2_000_000, 30, "sell")[0] is None
    buy_rows = [(1_000_001, 20.0, 30.0, "y"),      # taker BUY at/below our bid: lifts an offer, NOT a fill of a resting bid
                (1_000_002, 21.0, 30.0, "n"),      # taker SELL above our bid: hits a better bid, NOT a fill
                (1_000_003, 20.0, 30.0, "n")]      # taker SELL at our bid: FILL
    o, f25, _ = fill_times(buy_rows, 1_000_000, 2_000_000, 20, "buy")
    assert o == 1_000_003 and f25 == 1_000_003, "resting BUY: only a taker SELL (no) at yes_price <= d fills"
    assert fill_times(buy_rows[:2], 1_000_000, 2_000_000, 20, "buy")[0] is None
    assert FILL_TAKER_SIDE == {"sell": "y", "buy": "n"}
    return True


# ------------------------------------------------------------------------------------- study plan / quotes / tape
def study_series(sel):
    """Primary tier = mechanical passers.  Supplement tier = passes C1 and C2, fails ONLY C3 (exploratory, cannot PASS)."""
    prim = list(sel["passers"])
    supp = [r["series"] for r in sel["rows"] if r.get("failed") == ["C3"] and "screen" in r]
    return prim, supp


def cmd_plan():
    """plan <primary_tape_budget> <supplement_tape_budget>: events prefix per series, in the saved shuffle order, until the number of
    tape-eligible markets (lifetime volume > 0) reaches the budget or the events run out.  Outcome-free."""
    sel = jload(SELECTION)
    uni = jload(UNIVERSE)
    pb, sb = int(sys.argv[2]), int(sys.argv[3])
    prim, supp = study_series(sel)
    plan = jload(os.path.join(CACHE, "plan.json"), {"series": {}, "budgets": {}})
    plan["budgets"] = {"primary": pb, "supplement": sb}
    for tier, lst, budget in (("P", prim, pb), ("S", supp, sb)):
        for s in lst:
            if s in plan["series"] and plan["series"][s].get("complete"):
                continue
            evs = uni["series"][s]["events"]
            used, elig, mk = [], 0, 0
            for e in evs:
                if elig >= budget:
                    break
                ensure_event(e, s)
                ladder, _c = load_event(e)
                used.append(e)
                mk += len(ladder)
                elig += sum(1 for m in ladder if m["vol_life"] > 0)
            plan["series"][s] = {"tier": tier, "events": used, "tape_eligible": elig, "markets": mk, "complete": True,
                                 "universe_events": len(evs), "is_exact_prefix": used == evs[:len(used)]}
            jdump(plan, os.path.join(CACHE, "plan.json"))
            print("planned", tier, s, "events", len(used), "/", len(evs), "eligible", elig, "markets", mk, STATS, flush=True)


def cmd_place():
    plan = jload(os.path.join(CACHE, "plan.json"))
    qs, ex = [], collections.Counter()
    for s, pl in plan["series"].items():
        for e in pl["events"]:
            ladder, candles = load_event(e)
            q, x = place_event(e, ladder, candles)
            for r in q:
                r["series"] = s
            qs += q
            for kk, v in x.items():
                ex[(s,) + kk] += v
    assert all(q["stale"] is not None and q["stale"] >= 0 for q in qs), "look-ahead: a quote used a candle after its cutoff"
    assert all(q["bid"] is not None and q["ask"] is not None and 0 < q["bid"] < q["ask"] < 100 for q in qs), "a void quote leaked"
    blob = json.dumps(qs, sort_keys=True).encode()
    jdump({"quotes": qs, "excl": {"|".join(map(str, k)): v for k, v in ex.items()}, "sha256": hashlib.sha256(blob).hexdigest(),
           "series": list(plan["series"])}, QUOTES)
    print("quotes", len(qs), "sha", hashlib.sha256(blob).hexdigest()[:16], flush=True)


def tape_needed(qd):
    by = collections.defaultdict(dict)
    zero = collections.defaultdict(dict)
    for q in qd["quotes"]:
        (by if q["vol_life"] > 0 else zero)[q["event"]][q["ticker"]] = q["close_ts"]
    return by, zero


def cmd_tape():
    """Tape only for quoted tickers with lifetime volume > 0.  Lifetime volume 0 => no print exists (checked on a sample)."""
    MF.TS = TS                                          # the validated fetcher's window is close - max(TS)*60 - 60 (T=60 needs 61 min)
    qd = jload(QUOTES)
    by, zero = tape_needed(qd)
    plan = jload(os.path.join(CACHE, "plan.json"))
    order = []
    for s, pl in plan["series"].items():
        for e in pl["events"]:
            if e in by or e in zero:
                order.append(e)
    os.makedirs(TAPE, exist_ok=True)
    t0, n = time.time(), 0
    for e in order:
        p = os.path.join(TAPE, e + ".json")
        if os.path.exists(p) and jload(p).get("complete"):
            continue
        out = {}
        for tk, ct in sorted(by.get(e, {}).items()):
            try:
                rows, _pages = MF.fetch_ticker(tk, ct)
            except Exception as ex_:
                print("FAIL", tk, str(ex_)[:60], flush=True)
                out = None
                break
            out[tk] = rows
        if out is None:
            continue
        for tk in zero.get(e, {}):
            out[tk] = []
        jdump({"event": e, "complete": True, "fetched_at": int(time.time()), "tape": out}, p)
        n += 1
        if n % 10 == 0:
            print(f"tape events {n}/{len(order)}  {time.time() - t0:.0f}s  {STATS}  pace={PACE[0]:.2f}", flush=True)
    # zero-volume validation: a seeded sample of lifetime-volume-0 quoted tickers must have no prints
    zl = sorted((e, tk, ct) for e, d in zero.items() for tk, ct in d.items())
    rng = random.Random(SEED + 7)
    samp = rng.sample(zl, min(40, len(zl)))
    chk = []
    for e, tk, ct in samp:
        rows, _ = MF.fetch_ticker(tk, ct)
        chk.append({"ticker": tk, "prints": len(rows)})
    jdump({"n": len(chk), "with_prints": sum(1 for x in chk if x["prints"]), "rows": chk}, os.path.join(CACHE, "zero_volume_check.json"))
    print("tape done", STATS, "zero-volume check: prints in", sum(1 for x in chk if x["prints"]), "of", len(chk), flush=True)


def load_tapes(events):
    out = {}
    for e in events:
        p = os.path.join(TAPE, e + ".json")
        j = jload(p)
        if j and j.get("complete"):
            out[e] = j["tape"]
    return out


# ------------------------------------------------------------------------------------- statistics
def wilson_z(k, n, z):
    return TP.wilson(k, n, z) if n else (None, None, None)


def clustered(xs, groups, fam):
    cs = TP.cluster_stats(xs, [1.0] * len(xs), groups, fam=fam) if xs else {}
    return cs


def boot_diff(rows, model, side, key):
    """Cluster bootstrap (clusters = event or day) of P(loss|filled) - P(loss|quoted), in probability points; loss = YES for a
    sell, NO for a buy.  Returns [lo, hi, share_of_draws_with_a_fill] or None."""
    cl = sorted({r[key] for r in rows})
    agg = {c: np.zeros(4) for c in cl}
    for r in rows:
        v = agg[r[key]]
        loss = r["yes"] if side == "sell" else 1 - r["yes"]
        v[0] += 1
        v[1] += loss
        if r["fill"][side][model]:
            v[2] += 1
            v[3] += loss
    M = np.array([agg[c] for c in cl])
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(cl), size=(BOOT_B, len(cl)))
    S = M[idx].sum(axis=1)
    ok = (S[:, 2] > 0) & (S[:, 0] > 0)
    if not ok.any():
        return None
    diff = S[ok, 3] / S[ok, 2] - S[ok, 1] / S[ok, 0]
    return [float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5)), float(ok.mean())]


def cell_stats(rows, model, side, z_adj, fam):
    """rows: quotes of ONE (series, T, k) with 'yes' and fill flags; side: 'sell' or 'buy'.  Unfilled quotes stay in every
    denominator.  Loss event: YES for a sell, NO for a buy."""
    n = len(rows)
    pxk = "a" if side == "sell" else "d"
    filled = [r for r in rows if r["fill"][side][model]]
    nf = len(filled)
    kq = sum(r["yes"] for r in rows)
    kf = sum(r["yes"] for r in filled)
    pq, qlo, qhi = wilson_z(kq, n, 1.959963985)
    pf, flo, fhi = wilson_z(kf, nf, 1.959963985)
    _, flo_a, fhi_a = wilson_z(kf, nf, z_adj)
    mean_px_f = (sum(r[pxk] for r in filled) / nf) if nf else None
    if side == "sell":
        pnl = lambda r: (r["a"] - 100.0 * r["yes"])
        loss_q = pq
        loss_f = pf
        g1 = bool(nf and fhi_a * 100.0 < mean_px_f)
    else:
        pnl = lambda r: (100.0 * r["yes"] - r["d"])
        loss_q = None if pq is None else 1.0 - pq
        loss_f = None if pf is None else 1.0 - pf
        g1 = bool(nf and flo_a * 100.0 > mean_px_f)
    pnl_all = [pnl(r) if r["fill"][side][model] else 0.0 for r in rows]
    pnl_f = [pnl(r) for r in filled]
    ev_e = clustered(pnl_all, [r["event"] for r in rows], fam)
    ev_d = clustered(pnl_all, [r["day"] for r in rows], fam)
    evf_e = clustered(pnl_f, [r["event"] for r in filled], fam)
    ec = collections.Counter(r["event"] for r in filled)
    dc = collections.Counter(r["day"] for r in filled)
    ratio = (loss_f / loss_q) if (nf and loss_q and loss_q > 0) else None
    inside = [r for r in rows if (r["a"] < r["ask"] if side == "sell" else r["d"] > r["bid"])]
    inside_f = [r for r in inside if r["fill"][side][model]]
    fresh = [r for r in rows if r["stale"] <= 120]
    fresh_f = [r for r in fresh if r["fill"][side][model]]
    bo = bd = None
    if nf >= 20:
        bo, bd = boot_diff(rows, model, side, "event"), boot_diff(rows, model, side, "day")
    fill_rate = nf / n if n else None
    c = {"n_quoted": n, "k_yes_quoted": kq, "p_yes_quoted": pq, "q_lo": qlo, "q_hi": qhi,
         "n_filled": nf, "k_yes_filled": kf, "p_yes_filled": pf, "f_lo": flo, "f_hi": fhi, "f_lo_adj": flo_a, "f_hi_adj": fhi_a,
         "fill_rate": fill_rate, "mean_px_filled": mean_px_f, "breakeven": (mean_px_f / 100.0) if mean_px_f is not None else None,
         "mean_px_quoted": (sum(r[pxk] for r in rows) / n) if n else None,
         "loss_rate_quoted": loss_q, "loss_rate_filled": loss_f, "adverse_ratio": ratio,
         "events_quoted": len({r["event"] for r in rows}), "days_quoted": len({r["day"] for r in rows}),
         "events_filled": len(ec), "days_filled": len(dc),
         "max_event_share": (max(ec.values()) / nf) if nf else None, "max_day_share": (max(dc.values()) / nf) if nf else None,
         "ev_per_quoted": ev_e.get("mean"), "se_q_event": ev_e.get("se"), "t_q_event": ev_e.get("t"), "bar_t": ev_e.get("bar"),
         "se_q_day": ev_d.get("se"), "t_q_day": ev_d.get("t"),
         "ev_per_filled": evf_e.get("mean"), "se_f_event": evf_e.get("se"),
         "ev_ceiling_c": (fill_rate * mean_px_f) if nf else 0.0,
         "boot_event": bo, "boot_day": bd,
         "inside_quoted": len(inside), "inside_filled": len(inside_f),
         "inside_p_yes_filled": (sum(r["yes"] for r in inside_f) / len(inside_f)) if inside_f else None,
         "stale_gt120_share": (sum(1 for r in rows if r["stale"] > 120) / n) if n else None,
         "fresh_quoted": len(fresh), "fresh_filled": len(fresh_f),
         "fresh_p_yes_filled": (sum(r["yes"] for r in fresh_f) / len(fresh_f)) if fresh_f else None}
    c["gates"] = {"g1_bound_clears": g1,
                  "g2_fill_rate_ge_5pct": bool(fill_rate is not None and fill_rate >= 0.05),
                  "g3_n_floor": bool(nf >= 500 and len(ec) >= 100 and len(dc) >= 20),
                  "g4_ev_per_quoted_positive": bool(c["ev_per_quoted"] is not None and c["ev_per_quoted"] > 0),
                  "g5_concentration": bool(nf and c["max_event_share"] <= 0.05 and c["max_day_share"] <= 0.25)}
    c["gates"]["pass"] = all(c["gates"].values())
    return c


# ------------------------------------------------------------------------------------- anchors
def _names(node):
    s = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            s.add(n.id)
        elif isinstance(n, ast.Attribute):
            s.add(n.attr)
        elif isinstance(n, ast.arg):
            s.add(n.arg)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"[A-Za-z_]\w{0,20}", n.value):
            s.add(n.value)
    return s


def _is_ask(nm):
    return {x.lower() for x in nm if "ask" in x.lower() or x.lower() in ("ya", "_ya")}


def _is_bid(nm):
    return {x.lower() for x in nm if "bid" in x.lower() or x.lower() in ("yb", "_yb")}


def _enclosing(parents, node):
    while node in parents:
        node = parents[node]
        if isinstance(node, ast.FunctionDef):
            return node.name
    return None


def scan_source(src):
    """Raises AssertionError on: (e) any `100 - <ask>` / `1 - <ask>`; any mid computation (bid-ish and ask-ish names in one
    arithmetic expression, except a SUBTRACTION inside spread_c, or a mid-ish identifier); (d) a result / tape / fill / outcome
    name referenced inside a placement-path function; and the taker-side map or the fill predicate being wrong (anchor c)."""
    tree = ast.parse(src)
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    ev = {"n_binops": 0, "n_100_minus": 0, "n_mixed_in_spread_c": 0}
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp):
            ev["n_binops"] += 1
            nm = _names(n)
            if isinstance(n.op, ast.Sub) and isinstance(n.left, ast.Constant) and n.left.value in (100, 100.0, 1, 1.0):
                ev["n_100_minus"] += 1
                assert not _is_ask(_names(n.right)), f"(e) 100-ask expression at line {n.lineno}"
            if _is_ask(nm) and _is_bid(nm):
                fn = _enclosing(parents, n)
                assert fn in MIX_ALLOWED_IN and isinstance(n.op, ast.Sub), f"(e) bid and ask combined (mid/spread) outside spread_c at line {n.lineno}"
                ev["n_mixed_in_spread_c"] += 1
        if isinstance(n, (ast.Name, ast.arg)):
            ident = (n.id if isinstance(n, ast.Name) else n.arg).lower()
            assert not (ident == "mid" or ident.startswith("mid_") or ident.endswith("_mid") or "midpoint" in ident or "midprice" in ident), \
                f"(e) mid-ish identifier {ident!r} at line {n.lineno}"
    fdefs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for f in PLACEMENT_FUNCS:
        bad = _names(fdefs[f]) & FORBIDDEN_IN_PLACEMENT
        assert not bad, f"(d) placement-path function {f} references {sorted(bad)}"
    # (c) the taker-side map, statically and behaviourally
    assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "FILL_TAKER_SIDE" for t in n.targets)]
    assert len(assigns) == 1, "(c) FILL_TAKER_SIDE must be assigned exactly once"
    assert ast.literal_eval(assigns[0].value) == {"sell": "y", "buy": "n"}, "(c) taker-side map is wrong"
    ns = {"FILL_TAKER_SIDE": ast.literal_eval(assigns[0].value)}
    exec(compile(ast.Module([fdefs["qualifies"]], []), "<qualifies>", "exec"), ns)
    q = ns["qualifies"]
    assert q("y", 30.0, 30, "sell") and not q("n", 30.0, 30, "sell") and not q("y", 29.0, 30, "sell"), "(c) resting-SELL predicate wrong"
    assert q("n", 20.0, 20, "buy") and not q("y", 20.0, 20, "buy") and not q("n", 21.0, 20, "buy"), "(c) resting-BUY predicate wrong"
    return ev


def anchor_static_checks():
    src = open(os.path.abspath(__file__)).read()
    ev = scan_source(src)
    ev["placement_funcs"] = PLACEMENT_FUNCS
    ev["forbidden_names"] = sorted(FORBIDDEN_IN_PLACEMENT)
    assert_side_maps()
    ev["assert_side_maps"] = True
    # NEGATIVE CONTROLS on doctored copies: every one must raise
    doctored = {
        "d_result_in_entry_obs": src.replace('    cutoff = close_ts - T * 60\n    if open_ts is not None and open_ts >= cutoff:\n        return {"why": "not_open", "bid": None, "ask": None, "vol": 0.0, "stale": None}',
                                             '    cutoff = close_ts - T * 60\n    _leak = raw.get("result")\n    if open_ts is not None and open_ts >= cutoff:\n        return {"why": "not_open", "bid": None, "ask": None, "vol": 0.0, "stale": None}', 1),
        "d_RESULT_KEY_in_place_event": src.replace('    qs, ex = [], collections.Counter()\n    for m in ladder:\n        raw = candles.get(m["ticker"])',
                                                   '    qs, ex = [], collections.Counter()\n    _leak = RESULT_KEY\n    for m in ladder:\n        raw = candles.get(m["ticker"])', 1),
        "d_tape_in_make_quotes": src.replace('    if o["why"] != "ok":\n        return None, None, o["why"]\n    if o["bid"] is None',
                                             '    _leak = fill_times\n    if o["why"] != "ok":\n        return None, None, o["why"]\n    if o["bid"] is None', 1),
        "e_100_minus_ask": src.replace('    d = o["ask"] - k\n', '    d = 100 - o["ask"] - k\n', 1),
        "e_mid_price": src.replace('    a = o["bid"] + k\n', '    a = (o["bid"] + o["ask"]) // 2 + k\n', 1),
        "e_spread_outside_spread_c": src.replace('    a = o["bid"] + k\n', '    _s = o["ask"] - o["bid"]\n    a = o["bid"] + k\n', 1),
        "c_taker_side_map_swapped": src.replace('FILL_TAKER_SIDE = {"sell": "y", "buy": "n"}', 'FILL_TAKER_SIDE = {"sell": "n", "buy": "y"}', 1),
        "c_sell_predicate_uses_buy_side": src.replace('return side_char == FILL_TAKER_SIDE["sell"] and price >= px - 1e-9',
                                                      'return side_char == FILL_TAKER_SIDE["buy"] and price >= px - 1e-9', 1),
        "c_buy_predicate_wrong_price_side": src.replace('return side_char == FILL_TAKER_SIDE["buy"] and price <= px + 1e-9',
                                                        'return side_char == FILL_TAKER_SIDE["buy"] and price >= px - 1e-9', 1),
    }
    controls = {}
    for name, dsrc in doctored.items():
        assert dsrc != src, f"doctoring failed for {name}"
        try:
            scan_source(dsrc)
            controls[name] = "DID NOT RAISE"
        except AssertionError as e:
            controls[name] = "raised: " + str(e)[:100]
    assert all(v.startswith("raised") for v in controls.values()), controls
    ev["negative_controls"] = controls
    return ev


def side_convention_check(tapes, ladders, candles_by_event, nmax=200):
    """Empirical anchor (c): a taker SELL ('n') executes at the BID side of that minute's book, a taker BUY ('y') at the ASK side.
    For each print (bucketed into the candle minute (end-60s, end]), test whether yes_price lies inside that minute's yes_bid
    [low, high] or yes_ask [low, high] range (both-sided minutes only).  An inverted convention would invert this table."""
    stat = {s: collections.Counter() for s in ("n", "y")}
    for e in list(tapes)[:nmax]:
        cd = candles_by_event[e]
        lad = {m["ticker"]: m["close_ts"] for m in ladders[e]}
        for tk, rows in tapes[e].items():
            book = {}
            for c in cd.get(tk) or []:
                def rng(node):
                    if not node:
                        return None
                    lo, hi = node.get("low_dollars", node.get("low")), node.get("high_dollars", node.get("high"))
                    return None if lo is None or hi is None else (float(lo) * 100.0, float(hi) * 100.0)
                bb, aa = rng(c.get("yes_bid")), rng(c.get("yes_ask"))
                if bb and aa and bb[0] > 0 and aa[1] < 100:
                    book[c["end_period_ts"]] = (bb, aa)
            for ts, p, cnt, s in rows:
                if s not in stat or ts > (lad[tk] - 15 * 60) * 1_000_000:
                    continue
                bk = book.get((ts + 60_000_000 - 1) // 60_000_000 * 60)
                if not bk:
                    continue
                (bl, bh), (al, ah) = bk
                at_bid, at_ask = bl - 0.5 <= p <= bh + 0.5, al - 0.5 <= p <= ah + 0.5
                if at_bid and at_ask:
                    continue
                stat[s]["n_prints"] += 1
                stat[s]["contracts"] += cnt
                stat[s]["at_bid"] += at_bid
                stat[s]["at_ask"] += at_ask
    out = {}
    for s in ("n", "y"):
        n = stat[s]["n_prints"]
        out[s] = {"n_prints": n, "contracts": stat[s]["contracts"],
                  "share_in_bid_range": stat[s]["at_bid"] / n if n else None,
                  "share_in_ask_range": stat[s]["at_ask"] / n if n else None}
    return out


def cmd_raw():
    """Anchor (c) hand-work: re-pull RAW API rows for the first 10 N=25... optimistic fills per side (T=15, k=1) in plan order."""
    MF.TS = TS
    qd = jload(QUOTES)
    plan = jload(os.path.join(CACHE, "plan.json"))
    pos = {}
    for s, pl in plan["series"].items():
        for i, e in enumerate(pl["events"]):
            pos[e] = (list(plan["series"]).index(s), i)
    out = {"sell": [], "buy": []}
    tapes = {}
    cand = sorted([q for q in qd["quotes"] if q["T"] == 15 and q["k"] == 1], key=lambda q: (pos[q["event"]], q["ticker"]))
    for q in cand:
        if len(out["sell"]) >= 10 and len(out["buy"]) >= 10:
            break
        if q["event"] not in tapes:
            tp = jload(os.path.join(TAPE, q["event"] + ".json"))
            tapes[q["event"]] = tp["tape"] if tp and tp.get("complete") else {}
        rows = tapes[q["event"]].get(q["ticker"], [])
        t0, cl = (q["close_ts"] - 900) * 1_000_000, q["close_ts"] * 1_000_000
        for side, px in (("sell", q["a"]), ("buy", q["d"])):
            if len(out[side]) >= 10:
                continue
            if fill_times(rows, t0, cl, px, side)[0] is not None:
                out[side].append({"quote": q, "side": side, "px": px})
    res = {"sell": [], "buy": []}
    for side in ("sell", "buy"):
        for it in out[side]:
            q = it["quote"]
            lo, hi = q["close_ts"] - 60 * 60 - 60, q["close_ts"] + 120
            r = get(f"/markets/trades?ticker={q['ticker']}&min_ts={lo}&max_ts={hi}&limit=1000")
            res[side].append({"quote": q, "px": it["px"], "raw": r.get("trades", []), "cursor": r.get("cursor")})
    jdump(res, HAND_RAW)
    print("saved", {k: len(v) for k, v in res.items()})


def hand_worked_raw():
    """Re-derive each fill from the RAW rows, with the rule written out independently of `qualifies` / fill_times."""
    d = jload(HAND_RAW)
    if not d:
        return None
    out = {"sell": [], "buy": []}
    for side in ("sell", "buy"):
        for it in d[side]:
            q, px = it["quote"], it["px"]
            t0, cl = q["close_ts"] - 900, q["close_ts"]
            first, cum, ign_wrong_side, ok_pairs = None, 0.0, 0.0, True
            for t in sorted(it["raw"], key=lambda x: x["created_time"]):
                ts = MF.iso_us(t["created_time"]) / 1e6
                if ts <= t0 or ts > cl:
                    continue
                yp = round(float(t["yes_price_dollars"]) * 100, 4)
                npx = round(float(t["no_price_dollars"]) * 100, 4)
                ok_pairs &= abs(yp + npx - 100) < 1e-6
                cnt = float(t["count_fp"])
                if side == "sell":
                    price_ok = yp >= px
                    right_side = t["taker_side"] == "yes"
                else:
                    price_ok = yp <= px
                    right_side = t["taker_side"] == "no"
                if price_ok and right_side:
                    cum += cnt
                    if first is None:
                        first = {"created_time": t["created_time"], "taker_side": t["taker_side"], "yes_price_c": yp, "no_price_c": npx, "count": cnt}
                elif price_ok and not right_side:
                    ign_wrong_side += cnt
            out[side].append({"ticker": q["ticker"], "side": side, "quote_px_c": px, "bid": q["bid"], "ask": q["ask"], "cutoff_ts": t0,
                              "first_fill_print": first, "cum_qualifying": cum, "price_ok_but_wrong_taker_side_ignored": ign_wrong_side,
                              "yes_plus_no_is_100": ok_pairs, "cursor_more_pages": bool(it.get("cursor"))})
    return out
# __ANALYZE__


# ------------------------------------------------------------------------------------- analyze
def prefix_coverage(plan, qd, tape_events):
    """Per series: longest PREFIX of the saved shuffle order whose events are complete (no quote, or tape complete).  Events after
    the first gap are stragglers: excluded from analysis, counted, never re-ordered."""
    quoted_events = {q["event"] for q in qd["quotes"]}
    cov = {}
    for s, pl in plan["series"].items():
        ok = []
        for e in pl["events"]:
            if e in quoted_events and e not in tape_events:
                break
            ok.append(e)
        stray = [e for e in pl["events"][len(ok):] if (e not in quoted_events) or (e in tape_events)]
        cov[s] = {"events": ok, "stragglers": stray, "planned": len(pl["events"]), "universe": pl["universe_events"],
                  "covered_fraction_of_universe": len(ok) / pl["universe_events"] if pl["universe_events"] else None,
                  "exact_prefix_of_saved_order": ok == jload(UNIVERSE)["series"][s]["events"][:len(ok)]}
    return cov


def pooled_fill(cells, series, side, model):
    nq = nf = kq = kf = 0
    for key, c in cells.items():
        ss, T, k, sd, m = key.split("|")
        if ss == series and sd == side and m == model:
            nq += c["n_quoted"]
            nf += c["n_filled"]
            kq += c["k_yes_quoted"]
            kf += c["k_yes_filled"]
    if not nq:
        return {"n_quoted": 0}
    pq, pf = kq / nq, (kf / nf if nf else None)
    if side == "sell":
        lq, lf = pq, pf
    else:
        lq, lf = 1 - pq, (None if pf is None else 1 - pf)
    ratio = (lf / lq) if (nf and lq and lq > 0) else None
    return {"n_quoted": nq, "n_filled": nf, "fill_rate": nf / nq, "loss_q": lq, "loss_f": lf, "ratio": ratio}


def cmd_analyze():
    chk = anchor_static_checks()
    sel = jload(SELECTION)
    uni = jload(UNIVERSE)
    plan = jload(os.path.join(CACHE, "plan.json"))
    qd = jload(QUOTES)
    prim, supp = study_series(sel)
    comp = jload(os.path.join(CACHE, "comparisons.json"))
    assert comp["primary_series"] == prim, "comparison count was frozen for a different passer set"
    M_P = comp["M_primary"]
    M_S = comp["M_supplement"]
    z_P = float(st.norm.ppf(1 - 0.05 / max(1, M_P) / 2))
    z_S = float(st.norm.ppf(1 - 0.05 / max(1, M_S) / 2))
    tier_of = {s: pl["tier"] for s, pl in plan["series"].items()}

    # anchor (d): saved placement == fresh recomputation
    fresh = []
    for s, pl in plan["series"].items():
        for e in pl["events"]:
            ladder, candles = load_event(e)
            q, _x = place_event(e, ladder, candles)
            for r in q:
                r["series"] = s
            fresh += q
    assert hashlib.sha256(json.dumps(fresh, sort_keys=True).encode()).hexdigest() == qd["sha256"], "placement drifted"

    events_all = sorted({e for pl in plan["series"].values() for e in pl["events"]})
    tapes = load_tapes(events_all)                    # first moment the tape is read
    cov = prefix_coverage(plan, qd, set(tapes))
    keep_events = {s: set(c["events"]) for s, c in cov.items()}
    quotes = [q for q in qd["quotes"] if q["event"] in keep_events[q["series"]]]
    straggler_quotes = len(qd["quotes"]) - len(quotes)

    # fills (tape), still no outcome loaded
    for q in quotes:
        rows = tapes[q["event"]][q["ticker"]]
        t0, cl = (q["close_ts"] - q["T"] * 60) * 1_000_000, q["close_ts"] * 1_000_000
        f = {}
        for side, px in (("sell", q["a"]), ("buy", q["d"])):
            o, f25, f100 = fill_times(rows, t0, cl, px, side)
            f[side] = {"opt": o is not None, "n25": f25 is not None, "n100": f100 is not None}
        q["fill"] = f
    # empirical side-convention check + raw hand work (no outcome yet)
    lad_by = {e: load_event(e)[0] for e in tapes}
    cd_by = {e: load_event(e)[1] for e in tapes}
    conv = side_convention_check({e: tapes[e] for e in tapes}, lad_by, cd_by)
    hand = hand_worked_raw()
    # outcomes: first loaded here
    excl = collections.Counter()
    rows_ = []
    resmap = {e: load_results(e) for e in {q["event"] for q in quotes}}
    for q in quotes:
        r = resmap[q["event"]].get(q["ticker"])
        if r not in ("yes", "no"):
            excl["no_official_yes_no_result"] += 1
            continue
        q["yes"] = 1 if r == "yes" else 0
        rows_.append(q)

    cells = {}
    for s in plan["series"]:
        z = z_P if tier_of[s] == "P" else z_S
        fam = M_P if tier_of[s] == "P" else M_S
        sub_s = [r for r in rows_ if r["series"] == s]
        for T in TS:
            for k in KS:
                sub = [r for r in sub_s if r["T"] == T and r["k"] == k]
                for side in SIDES:
                    for m in MODELS:
                        cells[f"{s}|{T}|{k}|{side}|{m}"] = dict(cell_stats(sub, m, side, z, max(1, fam)), series=s, tier=tier_of[s], T=T, k=k, side=side, model=m)

    # verdict (primary tier only, N=25 decisive)
    prim_n25 = {key: c for key, c in cells.items() if c["tier"] == "P" and c["model"] == "n25"}
    passing = [key for key, c in prim_n25.items() if c["gates"]["pass"]]
    floor = [key for key, c in prim_n25.items() if c["gates"]["g3_n_floor"]]
    kill_each = {key: (not prim_n25[key]["gates"]["g1_bound_clears"]) for key in floor}
    verdict = "PASS" if passing else ("KILL" if (floor and all(kill_each.values())) else "INSUFFICIENT")
    sens = {}
    for m in ("opt", "n100"):
        d_ = {key: c for key, c in cells.items() if c["tier"] == "P" and c["model"] == m}
        p = [key for key, c in d_.items() if c["gates"]["pass"]]
        fl = [key for key, c in d_.items() if c["gates"]["g3_n_floor"]]
        sens[m] = {"pass": p, "floor": fl, "gate1_fails_in_every_floor_cell": bool(fl and all(not d_[k_]["gates"]["g1_bound_clears"] for k_ in fl))}
    supp_n25 = {key: c for key, c in cells.items() if c["tier"] == "S" and c["model"] == "n25"}
    supp_info = {"series": supp, "M_supplement": M_S,
                 "cells_gate1_clear": [k_ for k_, c in supp_n25.items() if c["gates"]["g1_bound_clears"]],
                 "cells_all_gates": [k_ for k_, c in supp_n25.items() if c["gates"]["pass"]],
                 "cells_meeting_floor": [k_ for k_, c in supp_n25.items() if c["gates"]["g3_n_floor"]]}
    # fill-rate ceiling from lifetime volume (a quote cannot fill unless a print exists)
    rep = {
        "spec": "WIDE_SPREAD_MAKER_SPEC.md", "verdict": verdict, "primary_series": prim, "supplement_series": supp,
        "comparisons": {"M_primary": M_P, "M_supplement": M_S, "per_series": 16, "frozen_at": comp["frozen_at_iso"], "z_adj_primary": z_P, "z_adj_supplement": z_S},
        "selection": {"n_series": sel["n_series"], "passers": prim, "tally": sel["tally"], "prefilter": sel["prefilter"], "params": sel["params"]},
        "coverage": cov, "sampling": {"quotes_total": len(qd["quotes"]), "quotes_analysed": len(quotes), "straggler_quotes": straggler_quotes,
                                      "quotes_with_result": len(rows_), "quotes_sha256": qd["sha256"]},
        "exclusions": {"placement": qd["excl"], "result": dict(excl)},
        "cells": cells, "pass_cells": passing, "floor_cells_n25": floor, "kill_cells_n25": kill_each, "sensitivity": sens, "supplement": supp_info,
        "anchors": {"static": chk, "side_convention": conv, "hand_worked_raw": hand, "zero_volume_check": jload(os.path.join(CACHE, "zero_volume_check.json"))},
    }
    jdump(rep, OUT_JSON)
    write_md(rep, sel, uni, plan)
    print("verdict", verdict, "quotes", len(quotes), "with result", len(rows_), "pass", len(passing), "floor", len(floor))
    return rep


# ------------------------------------------------------------------------------------- report
def _f(x, nd=2, pct=False):
    if x is None:
        return "n/a"
    return f"{x * 100:.{nd}f}%" if pct else f"{x:.{nd}f}"


def _ci(lo, hi):
    return "n/a" if lo is None else f"[{lo * 100:.2f}%, {hi * 100:.2f}%]"


def _sg(x):
    return "n/a" if x is None else ("+" if x > 0 else ("-" if x < 0 else "0"))


def write_md(rep, sel, uni, plan):
    C = rep["cells"]
    L = []
    prim, supp = rep["primary_series"], rep["supplement_series"]
    cm = rep["comparisons"]
    L.append("# Wide-spread maker: is there a sweet spot between spread and flow?  (WIDE_SPREAD_MAKER_SPEC.md, executed)\n")
    L.append(f"**VERDICT: {rep['verdict']}**  (frozen PASS/KILL rule applied verbatim; section 7)\n")
    L += PLAIN_READING_HOOK(rep)
    # ---------------------------------------------------------------- 1 selection
    L.append("\n## 1. Mechanical product selection and the comparison count (fixed BEFORE any gate was evaluated)\n")
    L += SELECTION_TEXT(rep, sel, uni)
    # ---------------------------------------------------------------- 2 anchor f
    L.append("\n## 2. Anchor (f): flow vs spread, jointly -- one row per tested series\n")
    L += F_TABLE(rep, sel)
    L.append("\n## 3. Anchor (a): adverse selection -- P(YES | filled) vs P(YES | quoted) vs break-even, BEFORE any EV\n")
    L += A_TABLES(rep)
    L.append("\n## 4. Anchor (b): quote, fill and fill-rate counts (unfilled quotes in every denominator); EV by sign\n")
    L += B_TABLES(rep)
    L.append("\n## 5. Anchors (c), (d), (e), (g)\n")
    L += CDEG(rep)
    L.append("\n## 6. Exclusions (count and reason)\n")
    L += EXCL(rep, sel, uni)
    L.append("\n## 7. Verdict: frozen rule, numbers beside each bar\n")
    L += VERDICT(rep)
    open(OUT_MD, "w").write("\n".join(L) + "\n")


def PLAIN_READING_HOOK(rep):
    return POST_RUN_TEXT.get("plain", [])


POST_RUN_TEXT: dict = {}                 # filled in by hand AFTER the run from the tables below (prose only; no bar depends on it)


# ------------------------------------------------------------------------------------- report sections
def _row_series(sel):
    return {r["series"]: r for r in sel["rows"]}


def SELECTION_TEXT(rep, sel, uni):
    L = []
    rows = sel["rows"]
    prim, supp = rep["primary_series"], rep["supplement_series"]
    cm = rep["comparisons"]
    nser = len(rows)
    L.append(f"**Universe.** {nser:,} series in the seven categories (Sports, Politics, Financials, Economics, Climate and Weather, Commodities, "
             f"**Elections**) that have at least one non-MVE event in the live partition (settled, last_updated >= {LIVE_CUT[:10]}); "
             f"{sum(len(v['events']) for v in uni['series'].values()):,} events. Events migrated to `/historical` before that date "
             f"({uni['events_historical_band_excluded']:,} in the walk, {sum(uni['historical_band_in_scope_categories'].values()):,} of them in these categories) "
             "are out of reach (one API call per market) and are NOT in the universe: this is the live window, the same window `CATALOG_CALIBRATION` used.\n")
    L.append("**Rule, applied literally and in this order** (details and every interpretation choice in the module docstring): "
             "C1 = >= 50 settled markets with an official yes/no `result` and an entry candle at T=15; "
             f"C2 = median `yes_ask - yes_bid` >= {SPREAD_BAR}c at T=15 over entry candles with both sides quoted; "
             "C3 = median entry-candle `volume_fp` > 0 over markets with an entry candle. "
             "Medians are over the frozen-shuffled events screened for each series until 50 covered markets (cap "
             f"{EVENT_CAP} events). Series whose lifetime volume already forces C3 to fail are excluded without candles (the bound is validated in section 5).\n")
    # tally table
    tally = collections.Counter()
    for r in rows:
        key = r["status"] if r["status"] != "EXCLUDED" else "EXCLUDED:" + "+".join(r["failed"])
        tally[(r["cat"], key)] += 1
    keys = sorted({k for _, k in tally})
    cats = sorted({c for c, _ in tally})
    L.append("| category | series | " + " | ".join(keys) + " |")
    L.append("|---|--:|" + "--:|" * len(keys))
    for c in cats + ["ALL"]:
        cnt = [tally.get((c, k), 0) if c != "ALL" else sum(v for (cc, kk), v in tally.items() if kk == k) for k in keys]
        L.append(f"| {c} | {sum(cnt):,} | " + " | ".join(f"{x:,}" for x in cnt) + " |")
    L.append("\n`EXCLUDED:C1` = fewer than 50 settled yes/no markets (or, after screening, fewer than 50 covered); `EXCLUDED:C3` = lifetime volume bound "
             "(C3 implied, C2 not evaluated) or a screened series whose median entry volume is 0 while C1 and C2 hold; `EXCLUDED:C2+C3` etc. = screened series failing several. "
             "`UNRESOLVED_CAP` = event cap hit before 50 covered markets (neither passed nor failed C1).\n")
    # screened series table
    scr = [r for r in rows if "screen" in r]
    L.append(f"\n### 1a. Every series that reached the candle screen ({len(scr)}), with the criterion that excluded it\n")
    L.append("| series | category | settled yes/no | L+ (ever traded) | events screened | covered | both-sided | median spread (c) | median entry vol | share entry vol>0 | C1 | C2 | C3 | status |")
    L.append("|---|---|--:|--:|--:|--:|--:|--:|--:|--:|:-:|:-:|:-:|---|")
    for r in sorted(scr, key=lambda r: (r["status"] != "PASS_SELECTION", r["failed"] != ["C3"], r["series"])):
        sc, ls = r["screen"], r["listing"]
        f = r.get("failed", [])
        mark = lambda c: "fail" if c in f else ("-" if r["status"] == "UNRESOLVED_CAP" and c == "C1" else "ok")
        flags = ""
        if sc["boundary_median_vol"]:
            flags += " (C3 positive only via even-n median averaging)"
        if sc["thin_two_sided"]:
            flags += " (thin: <10 both-sided)"
        L.append(f"| {r['series']} | {r['cat']} | {ls['n_yes_no']:,} | {_f(ls['L_plus'], 0, True)} | {sc['events_screened']} | {sc['covered']} | {sc['both_sided']} | "
                 f"{_f(sc['median_spread'], 1)} | {_f(sc['median_entry_vol'], 2)} | {_f(sc['share_entry_vol_pos'], 0, True)} | {mark('C1')} | {mark('C2')} | {mark('C3')} | {r['status']}{flags} |")
    L.append(f"\n**Mechanical result: {len(prim)} series pass all three criteria: {', '.join(prim) if prim else 'NONE'}.**\n")
    L.append("### 1b. The comparison count (written to `cache/wide_maker/comparisons.json` at selection time, before any quote, tape or outcome existed)\n")
    L.append(f"* Passing series P = **{len(prim)}**.  Family = P x 2 k x 2 T x 2 sides x 2 fill models (optimistic, pessimistic N=25) = **M = {cm['M_primary']}** comparisons "
             f"(frozen at {cm['frozen_at']}). N=100 is disclosed beside it as a sensitivity and is not in the family.")
    L.append(f"* Bonferroni-adjusted Wilson intervals use z = Phi^-1(1 - 0.05/{max(1, cm['M_primary'])}/2) = {cm['z_adj_primary']:.3f}.")
    if supp:
        L.append(f"* EXPLORATORY supplement (not in the frozen selection, cannot produce a PASS): {len(supp)} series that pass C1 and C2 but fail ONLY C3 on the "
                 f"one-minute entry-candle definition; own count M_S = {cm['M_supplement']}, z = {cm['z_adj_supplement']:.3f}. Explained in section 2.")
    return L


def F_TABLE(rep, sel):
    L = []
    rs = _row_series(sel)
    C = rep["cells"]
    cov = rep["coverage"]
    tested = [s for s in rep["primary_series"]] + [s for s in rep["supplement_series"] if s in cov]
    if not tested:
        L.append("No series passed the mechanical selection and none qualifies for the exploratory supplement: there is no flow-vs-spread row to report from the tape. "
                 "The spread side of the table for every series that reached the candle screen is in section 1a.")
        return L
    L.append("`tier P` = passes the frozen C1+C2+C3; `tier S` = EXPLORATORY: passes C1 and C2 but fails C3 (median volume of the single entry minute is 0). "
             "S exists because C3 as written (one-minute candle) is 0 for nearly every book on the venue, KXBTCD included (section 5); S rows can inform the sweet-spot question "
             "but cannot produce a PASS and do not enter the verdict.\n")
    L.append("**f-1. Spread and flow at the entry** (screen sample; lifetime columns from the full series listing):\n")
    L.append("| series | tier | category | events tested / universe | exact prefix | median spread (c) | median entry-minute vol | share entry vol>0 | lifetime vol (median / mean) | L+ ever traded | quotes (T=15,k=1) | strictly-inside share |")
    L.append("|---|:-:|---|--:|:-:|--:|--:|--:|--:|--:|--:|--:|")
    for s in tested:
        r = rs[s]
        sc, ls = r["screen"], r["listing"]
        cv = cov[s]
        c = C.get(f"{s}|15|1|sell|opt")
        nq = c["n_quoted"] if c else 0
        ins = (c["inside_quoted"] / c["n_quoted"]) if c and c["n_quoted"] else None
        L.append(f"| {s} | {rep_tier(rep, s)} | {r['cat']} | {len(cv['events'])} / {cv['universe']} ({_f(cv['covered_fraction_of_universe'], 1, True)}) | {'yes' if cv['exact_prefix_of_saved_order'] else 'NO'} | "
                 f"{_f(sc['median_spread'], 1)} | {_f(sc['median_entry_vol'], 2)} | {_f(sc['share_entry_vol_pos'], 0, True)} | {_f(ls['median_life_vol'], 0)} / {_f(ls['mean_life_vol'], 0)} | {_f(ls['L_plus'], 0, True)} | {nq:,} | {_f(ins, 0, True)} |")
    L.append("\n**f-2. Fill rate and adverse-selection ratio**, pooled over the four (T, k) cells of each side (each cell is its own set of quote instances; unfilled quotes in every denominator). "
             "Adverse ratio = P(loss event | filled) / P(loss event | quoted), loss event = YES for a sell, NO for a buy; > 1 means fills are worse than the quote population, "
             "and the spread pays only if the ratio stays below the break-even ratio shown in section 3.\n")
    L.append("| series | tier | side | quotes | fill rate opt | fill rate N=25 | fill rate N=100 | P(loss\\|quoted) | P(loss\\|filled) opt | ratio opt | P(loss\\|filled) N=25 | ratio N=25 |")
    L.append("|---|:-:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for s in tested:
        for side in SIDES:
            po, p25, p100 = (pooled_fill(C, s, side, m) for m in MODELS)
            L.append(f"| {s} | {rep_tier(rep, s)} | {side} | {po.get('n_quoted', 0):,} | {_f(po.get('fill_rate'), 2, True)} | {_f(p25.get('fill_rate'), 2, True)} | {_f(p100.get('fill_rate'), 2, True)} | "
                     f"{_f(po.get('loss_q'), 1, True)} | {_f(po.get('loss_f'), 1, True)} | {_f(po.get('ratio'), 2)} | {_f(p25.get('loss_f'), 1, True)} | {_f(p25.get('ratio'), 2)} |")
    return L


def rep_tier(rep, s):
    return "P" if s in rep["primary_series"] else "S"


def _cell_line(c, with_series=True):
    bd = c["boot_event"]
    bs = "n/a" if not bd else f"[{bd[0] * 100:+.1f}, {bd[1] * 100:+.1f}]"
    gap = None if not c["n_filled"] else (c["p_yes_filled"] - c["breakeven"]) * 100
    # profitable-direction margin: sell wins when P(YES|filled) < break-even; buy wins when P(YES|filled) > break-even
    return (f"| {c['T']} | {c['k']} | {c['side']} | {c['n_quoted']:,} | {_f(c['p_yes_quoted'], 1, True)} | {c['n_filled']:,} | "
            f"{_f(c['p_yes_filled'], 1, True)} {_ci(c['f_lo'], c['f_hi'])} | {_ci(c['f_lo_adj'], c['f_hi_adj'])} | {_f(c['breakeven'], 1, True)} | "
            f"{'n/a' if gap is None else f'{gap:+.1f}'} | {_f(c['adverse_ratio'], 2)} | {bs} | {c['fresh_filled']} / {_f(c['fresh_p_yes_filled'], 0, True)} | {'Y' if c['gates']['g1_bound_clears'] else 'n'} |")


def A_TABLES(rep):
    L = []
    C = rep["cells"]
    L.append("Per cell: P(YES | quoted) is the base rate of the quote population; P(YES | filled) the rate among filled quotes; break-even = mean quoted price of the filled "
             "quotes / 100 (a fee-free sell loses when P(YES | filled) is above it, a buy when below). `gap` = P(YES | filled) - break-even in points: **negative is the profit direction for a sell, positive for a buy.** "
             "Wilson 95% beside the Bonferroni-adjusted Wilson; `event-bootstrap` = 95% interval of P(loss | filled) - P(loss | quoted) in points resampling whole events "
             f"({BOOT_B} draws, seed {BOOT_SEED}; only when >= 20 fills); `g1` = the frozen gate-1 test (adjusted bound on the correct side of break-even). "
             "Cells with zero fills are listed as such: they are still cells.\n")
    for tier, ser in (("P", rep["primary_series"]), ("S", rep["supplement_series"])):
        for s in ser:
            if f"{s}|15|1|sell|n25" not in C:
                continue
            for m in ("n25", "opt"):
                cells = [C[f"{s}|{T}|{k}|{side}|{m}"] for T in TS for k in KS for side in SIDES]
                if tier == "S" and max(c["n_filled"] for c in cells) < 20 and m == "opt":
                    continue
                if tier == "S" and m == "opt" and max(c["n_filled"] for c in cells) < 30:
                    continue
                L.append(f"\n#### {s}  (tier {tier})  --  {MODEL_LABEL[m]}{'  (DECISIVE)' if m == 'n25' and tier == 'P' else ''}\n")
                L.append("| T | k | side | quoted n | P(YES\\|quoted) | filled n | P(YES\\|filled) [95%] | [Bonf. adj.] | break-even | gap (pp) | adverse ratio | event-bootstrap diff (pp) | fresh<=120s: fills / P(YES\\|filled) | g1 |")
                L.append("|--:|--:|---|--:|--:|--:|---|---|--:|--:|--:|---|--:|:-:|")
                for c in cells:
                    L.append(_cell_line(c))
    return L


def B_TABLES(rep):
    L = []
    C = rep["cells"]
    L.append("Counts first, EV second.  EV is **sign only** here (the SE is for information; there is no EV t gate and the next paragraph says why).  `EV/quoted` = sum of P&L over filled quotes / ALL quotes (unfilled = 0); "
             "`EV/filled` = mean P&L of the filled quotes; both in cents per contract, fee-free (maker fee is 0 on quadratic series).\n")
    for tier, ser in (("P", rep["primary_series"]), ("S", rep["supplement_series"])):
        for s in ser:
            if f"{s}|15|1|sell|n25" not in C:
                continue
            L.append(f"\n#### {s}  (tier {tier})\n")
            L.append("| T | k | side | quotes | events | days | opt fills (rate) | N=25 fills (rate) | N=25 events / days filled | N=100 fills (rate) | EV/quoted opt | EV/quoted N=25 (SE event) | EV/filled N=25 | max event / day share of fills |")
            L.append("|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|:-:|--:|:-:|--:|")
            for T in TS:
                for k in KS:
                    for side in SIDES:
                        o, a, b = (C[f"{s}|{T}|{k}|{side}|{m}"] for m in ("opt", "n25", "n100"))
                        if tier == "S" and max(o["n_filled"], a["n_filled"]) == 0 and k == 2:
                            continue
                        L.append(f"| {T} | {k} | {side} | {o['n_quoted']:,} | {o['events_quoted']} | {o['days_quoted']} | {o['n_filled']:,} ({_f(o['fill_rate'], 1, True)}) | {a['n_filled']:,} ({_f(a['fill_rate'], 1, True)}) | "
                                 f"{a['events_filled']} / {a['days_filled']} | {b['n_filled']:,} ({_f(b['fill_rate'], 1, True)}) | {_sg(o['ev_per_quoted'])} | {_sg(a['ev_per_quoted'])} ({_f(a['se_q_event'], 3)}) | {_sg(a['ev_per_filled'])} | "
                                 f"{_f(a['max_event_share'], 1, True)} / {_f(a['max_day_share'], 1, True)} |")
    # t cannot reach a bar
    L.append("\n**Why there is no EV t gate, in this data.**  The t-statistic of per-quoted EV is bounded by the arithmetic of a rare, bounded payoff: with fill rate f and mean price p "
             "the per-quoted EV can never exceed f x p cents (every fill wins), and its event-clustered SE is not smaller than the spread of the few fills. "
             "Cells with at least one N=25 fill, comparing the EV needed to reach the Bonferroni-corrected t bar with that ceiling:\n")
    L.append("| series | T | k | side | fills | EV ceiling f x p (c) | SE (event, c) | t bar | EV needed = bar x SE (c) | needed / ceiling |")
    L.append("|---|--:|--:|---|--:|--:|--:|--:|--:|--:|")
    shown = 0
    for key, c in C.items():
        if c["model"] != "n25" or c["tier"] != "P" or not c["n_filled"] or c["se_q_event"] is None or c["bar_t"] is None:
            continue
        need = c["bar_t"] * c["se_q_event"]
        L.append(f"| {c['series']} | {c['T']} | {c['k']} | {c['side']} | {c['n_filled']} | {c['ev_ceiling_c']:.3f} | {c['se_q_event']:.3f} | {c['bar_t']:.2f} | {need:.3f} | {_f(need / c['ev_ceiling_c'] if c['ev_ceiling_c'] else None, 2)} |")
        shown += 1
    if not shown:
        L.append("| (no primary-tier cell has an N=25 fill) | | | | | | | | | |")
    return L


def CDEG(rep):
    L = []
    a = rep["anchors"]
    st_ = a["static"]
    C = rep["cells"]
    L.append("**(c) Taker side per direction.** A resting SELL fills on a taker BUY (`taker_side = \"yes\"`) at `yes_price >= a`; a resting BUY fills on a taker SELL (`taker_side = \"no\"`) at `yes_price <= d`. "
             "`FILL_TAKER_SIDE = {\"sell\": \"y\", \"buy\": \"n\"}` is asserted statically (AST literal), behaviourally (`assert_side_maps()` on synthetic prints, each direction rejecting the other direction's prints) "
             "and with negative controls on doctored copies, all of which must raise:\n")
    L.append("| doctored copy | result |")
    L.append("|---|---|")
    for k, v in st_["negative_controls"].items():
        L.append(f"| `{k}` | {v} |")
    L.append(f"\nWhole-module scan: {st_['n_binops']} arithmetic expressions inspected; {st_['n_100_minus']} of the form `100 - x`, none with an ask-like `x`; "
             f"{st_['n_mixed_in_spread_c']} bid-and-ask expression, inside `spread_c` (the criterion-2 statistic) only; no mid-ish identifier anywhere.")
    sc_ = a["side_convention"]
    L.append("\nEmpirical convention check on THIS tape (each print bucketed into its candle minute; both-sided minutes only; prints before T=15 so the candle book is the live book): "
             "a taker SELL (`no`) should sit inside that minute's yes_bid range and a taker BUY (`yes`) inside the yes_ask range.\n")
    L.append("| taker_side | prints tested | contracts | in yes_bid range | in yes_ask range |")
    L.append("|---|--:|--:|--:|--:|")
    for s_, nm in (("n", "no (taker sells)"), ("y", "yes (taker buys)")):
        d = sc_[s_]
        L.append(f"| {nm} | {d['n_prints']:,} | {d['contracts']:,.0f} | {_f(d['share_in_bid_range'], 1, True)} | {_f(d['share_in_ask_range'], 1, True)} |")
    hw = a["hand_worked_raw"]
    L.append("\nHand-worked fills from RAW tape JSON (re-pulled from `GET /markets/trades`; first ten optimistic fills per side at T=15, k=1 in plan order; rule re-derived independently of `qualifies`). "
             "`wrong-side ignored` = contracts printed at a qualifying PRICE but with the other taker side, which a side-blind copy would have counted:\n")
    for side in SIDES:
        rows = (hw or {}).get(side, [])
        L.append(f"\n{side.upper()} ({len(rows)} of 10 available)\n")
        L.append("| ticker | quote px (c) | bid / ask at entry | first filling print (UTC) | taker_side | yes_price (c) | no_price (c) | count | yes+no=100 | qualifying contracts to close | wrong-side ignored |")
        L.append("|---|--:|--:|---|---|--:|--:|--:|:-:|--:|--:|")
        for r in rows:
            f = r["first_fill_print"] or {}
            L.append(f"| {r['ticker']} | {r['quote_px_c']} | {r['bid']} / {r['ask']} | {f.get('created_time', 'n/a')} | {f.get('taker_side', 'n/a')} | {f.get('yes_price_c', 'n/a')} | {f.get('no_price_c', 'n/a')} | "
                     f"{f.get('count', 'n/a')} | {'Y' if r['yes_plus_no_is_100'] else 'N'} | {r['cum_qualifying']:.0f} | {r['price_ok_but_wrong_taker_side_ignored']:.0f} |")
    L.append("\n**(d) No look-ahead, no outcome in placement.** Placement functions " + ", ".join(f"`{f}`" for f in st_["placement_funcs"]) +
             " reference none of: " + ", ".join(f"`{x}`" for x in st_["forbidden_names"]) + ". Placement is a separate pass (`place`) that writes `quotes.json` before the tape or any result is read; "
             "`analyze` recomputes it from the candle cache and asserts the sha256 equals the saved one, and asserts every quote's entry-candle age is >= 0. "
             f"Quotes sha256 `{rep['sampling']['quotes_sha256'][:16]}`. Queue depth is NOT observed in any archive: N is an explicit assumption (25, 100), the optimistic model is front of queue.")
    L.append("\n**(e) Both sides quoted; empty ask prints as 100c.** A side is a quote only if its printed price is strictly inside (0, 100); `yes_ask = 100` is how an EMPTY ask prints and is NOT a quote, `yes_bid = 0` is an empty bid. "
             "A quote anchored on an absent side is void, a crossed or locked candle is void, and a derived price outside 1..99 is void. Void quotes by reason (all series, T, k; each is still a market-T-k observation counted here, not silently dropped):\n")
    ex = collections.Counter()
    for k_, v in rep["exclusions"]["placement"].items():
        ex[k_.split("|")[-1]] += v
    L.append("| reason | count |")
    L.append("|---|--:|")
    for k_, v in sorted(ex.items()):
        L.append(f"| {k_} | {v:,} |")
    L.append("\n**(g) Size not measured.** Candles carry no depth, `yes_bid_size_fp` / `yes_ask_size_fp` exist on open markets only and cannot be backfilled, and a candle's volume is the total of that minute. "
             "Everything here is a count of quotes of ONE contract; volume figures are upper bounds on what a quote could have been filled for, and a real order size is not tested.")
    zc = a.get("zero_volume_check") or {}
    L.append(f"\nLifetime-volume-0 shortcut: quoted tickers whose listing `volume_fp` is 0 were given an empty tape without a call (no print can exist). Validation on a seeded sample: "
             f"{zc.get('with_prints', 'n/a')} of {zc.get('n', 'n/a')} fetched tapes contained any print.")
    return L


def EXCL(rep, sel, uni):
    L = []
    rows = sel["rows"]
    L.append(f"* Series universe {len(rows):,}; selection exclusions by category and criterion are in section 1; the per-series list is in the appendix and in `out/wide_spread_maker.json` (`selection.rows`).")
    s = rep["sampling"]
    L.append(f"* Study quotes placed {s['quotes_total']:,}; excluded as stragglers (events after the first gap in the saved order): {s['straggler_quotes']:,}; with an official yes/no result {s['quotes_with_result']:,}; "
             f"no official yes/no result: {rep['exclusions']['result'].get('no_official_yes_no_result', 0):,}.")
    cv = rep["coverage"]
    L.append("* Coverage per tested series (frozen shuffle; whole events; 'exact prefix' = the analysed events are exactly the first n of the saved order):\n")
    L.append("| series | tier | events analysed | planned | universe | covered fraction | exact prefix | stragglers |")
    L.append("|---|:-:|--:|--:|--:|--:|:-:|--:|")
    for ss, c in cv.items():
        L.append(f"| {ss} | {rep_tier(rep, ss)} | {len(c['events'])} | {c['planned']} | {c['universe']} | {_f(c['covered_fraction_of_universe'], 1, True)} | {'yes' if c['exact_prefix_of_saved_order'] else 'NO'} | {len(c['stragglers'])} |")
    L.append("\n### Appendix: every excluded series, by category and reason (comma separated)\n")
    by = collections.defaultdict(list)
    for r in rows:
        if r["status"] == "PASS_SELECTION":
            continue
        by[(r["cat"], r["status"] + (":" + "+".join(r["failed"]) if r["status"] == "EXCLUDED" else ""))].append(r["series"])
    for (cat, reason), lst in sorted(by.items()):
        L.append(f"* **{cat} / {reason}** ({len(lst)}): " + ", ".join(sorted(lst)))
    return L


def VERDICT(rep):
    L = []
    C = rep["cells"]
    cm = rep["comparisons"]
    prim = rep["primary_series"]
    floor, passing = rep["floor_cells_n25"], rep["pass_cells"]
    L.append(f"* Passing series (frozen selection): **{len(prim)}**; comparisons M = **{cm['M_primary']}**; cells in the verdict family under N=25: {len([k for k, c in C.items() if c['tier'] == 'P' and c['model'] == 'n25'])} (series x T x k x side).")
    n25 = {k: c for k, c in C.items() if c["tier"] == "P" and c["model"] == "n25"}
    L.append("\nPASS gates, counted over the primary-tier cells under pessimistic N=25 (a PASS needs ONE cell with all five):\n")
    L.append("| gate | bar | cells meeting it | best value |")
    L.append("|---|---|--:|---|")
    if n25:
        cnt = lambda g: sum(1 for c in n25.values() if c["gates"][g])
        bestfill = max(n25.values(), key=lambda c: c["fill_rate"] or 0)
        bestn = max(n25.values(), key=lambda c: c["n_filled"])
        L.append(f"| 1. adjusted Wilson bound clears break-even (sell: upper < a/100; buy: lower > d/100) | profit direction | {cnt('g1_bound_clears')} | n/a (a count) |")
        L.append(f"| 2. fill rate >= 5% of quotes | 5% | {cnt('g2_fill_rate_ge_5pct')} | {_f(bestfill['fill_rate'], 2, True)} ({bestfill['series']} T={bestfill['T']} k={bestfill['k']} {bestfill['side']}) |")
        L.append(f"| 3. n >= 500 filled, >= 100 events, >= 20 days | 500 / 100 / 20 | {cnt('g3_n_floor')} | {bestn['n_filled']} fills, {bestn['events_filled']} events, {bestn['days_filled']} days ({bestn['series']} T={bestn['T']} k={bestn['k']} {bestn['side']}) |")
        L.append(f"| 4. EV per quoted > 0 by sign | > 0 | {cnt('g4_ev_per_quoted_positive')} | sign only |")
        L.append(f"| 5. no event > 5% and no day > 25% of fills | 5% / 25% | {cnt('g5_concentration')} | |")
        L.append(f"| all five | | {len(passing)} | |")
    else:
        L.append("| (no primary-tier cell exists: zero series passed the mechanical selection) | | 0 | |")
    L.append(f"\nKILL clause (one-sided failure-to-clear): applies only to cells meeting the n floor (gate 3). Cells meeting the floor: **{len(floor)}**.")
    if floor:
        L.append("\n| cell | filled | events / days | P(YES\\|filled) | adjusted Wilson | break-even | gate 1 | fails to clear |")
        L.append("|---|--:|--:|---|---|--:|:-:|:-:|")
        for k_ in floor:
            c = C[k_]
            L.append(f"| {k_} | {c['n_filled']} | {c['events_filled']} / {c['days_filled']} | {_f(c['p_yes_filled'], 1, True)} | {_ci(c['f_lo_adj'], c['f_hi_adj'])} | {_f(c['breakeven'], 1, True)} | {'Y' if c['gates']['g1_bound_clears'] else 'n'} | {'YES' if rep['kill_cells_n25'][k_] else 'no'} |")
    else:
        L.append("With no cell meeting the n floor the KILL clause has nothing to apply to and cannot fire, exactly as in MAKER_FILL and FAVOURITE_MAKER. PASS needs a floor cell too.")
    L.append(f"\n**Frozen verdict: {rep['verdict']}.**")
    sv = rep["sensitivity"]
    L.append(f"\nSensitivity (disclosed, not decisive): optimistic model: {len(sv['opt']['floor'])} floor cells, {len(sv['opt']['pass'])} passing; N=100: {len(sv['n100']['floor'])} floor cells, {len(sv['n100']['pass'])} passing.")
    sp = rep["supplement"]
    if sp["series"]:
        L.append(f"\nExploratory supplement (tier S, {len(sp['series'])} series, M_S = {sp['M_supplement']}; cannot PASS): cells meeting the n floor under N=25: {len(sp['cells_meeting_floor'])}; "
                 f"cells whose adjusted Wilson bound clears break-even in the profit direction: {len(sp['cells_gate1_clear'])}; cells passing all five gates: {len(sp['cells_all_gates'])}.")
        if sp["cells_gate1_clear"]:
            L.append("\nThese S cells cleared gate 1 and are listed ONLY so they can be scrutinised, not promoted. With the comparison count above, ANY of them is exactly the 'one series squeaks past on a large count' case: "
                     + ", ".join(sp["cells_gate1_clear"]) + ".")
    return L


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    {"universe": cmd_universe, "list": cmd_list, "screen": cmd_screen, "selection": cmd_selection, "plan": cmd_plan,
     "place": cmd_place, "tape": cmd_tape, "raw": cmd_raw, "analyze": cmd_analyze, "checks": lambda: print(json.dumps(anchor_static_checks(), indent=1))}[c]()
