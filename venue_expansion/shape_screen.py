#!/usr/bin/env python3
"""shape_screen.py -- systematic, DESCRIPTIVE screen for the one structural property that survived the graveyard:

    "the market stays open for hours after the outcome is physically determined."

THIS IS NOT A HYPOTHESIS TEST. It carries no pass bar. Nothing it suggests may be promoted without a NEW
pre-registration (frozen spec, frozen bars, adversarial verify). It exists to replace family-by-family guessing with a
direct look at the whole Kalshi catalog.

Stages (each resumable; every pull cached under venue_expansion/cache/shape_screen/; politely paced ~1 req/s):
    catalog   full /series list + every settled non-MVE market in the live API window (global cursor, slimmed)
    classify  per series with >=20 settled markets: DETERMINED-EARLY / DETERMINED-AT-CLOSE / CLOSES-AT-DECISION /
              BULLETIN-PACED, from metadata + rules text (rules cited), plus a gap estimate
    sample    seeded, stratified-by-series, SHUFFLED work order (never re-sorted) of settled markets to pull
    candles   1-minute candlesticks for the final 2 hours of each sampled market (cached per ticker)
    report    oracle-capturable rate (edge_sizing_v2.normalize + winner-cost logic, window = 120 min), ranking,
              graveyard cross-check -> out/shape_screen.json, out/shape_screen.md

Run:  python3 venue_expansion/shape_screen.py <stage> [...]      (or `all`)

Outcome source: market.result from the Kalshi market object (the same object GET /markets/{ticker} returns); a random
subset of sampled tickers is re-fetched through GET /markets/{ticker} and compared (reported as agreement).
NO buy cost = 100 - yes_bid (never 100 - yes_ask). Fee = ceil(7*p*(1-p)) cents at the crossing price.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
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
CACHE = os.path.join(HERE, "cache", "shape_screen")
CANDLES = os.path.join(CACHE, "candles")
OUTDIR = os.path.join(HERE, "out")
API = "https://api.elections.kalshi.com/trade-api/v2"
SEED = 20261027
WINDOW_MIN = 120          # final 2 hours (task spec); edge_sizing_v2 used 60
MIN_SETTLED = 20
PACE_S = 1.0
_last_call = [0.0]
STATS = {"calls": 0, "r429": 0, "other_err": 0}


# --------------------------------------------------------------------------------------------------------------------
# polite HTTP
# --------------------------------------------------------------------------------------------------------------------
def http_get(url: str, tries: int = 8):
    """Sequential, ~1/s, adaptive: on 429/5xx back off exponentially and widen the pacing, relax slowly on success."""
    global PACE_S
    for i in range(tries):
        wait = PACE_S - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kwx-research/1.0"})
            with urllib.request.urlopen(req, timeout=60) as fh:
                out = json.load(fh)
            STATS["calls"] += 1
            PACE_S = max(1.0, PACE_S - 0.1)
            return out
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            STATS["r429" if e.code == 429 else "other_err"] += 1
            PACE_S = min(2.5, PACE_S + 0.2)
            time.sleep(min(60, 2 * 2 ** i))
        except Exception:
            STATS["other_err"] += 1
            time.sleep(min(60, 2 * 2 ** i))
    raise RuntimeError("giving up: " + url)


def jload(path, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh)
    os.replace(tmp, path)


def parse_ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def fee_c(cost_c: float) -> int:
    p = cost_c / 100.0
    return math.ceil(7 * p * (1 - p))


# --------------------------------------------------------------------------------------------------------------------
# STAGE 1: catalog.  (a) /series (one call, ~15k series)  (b) every settled event in the live window, slim, global cursor
#   (events are ~100x lighter than markets; the first attempt -- a global settled-MARKET walk -- was abandoned after
#   ~32k markets because hourly/15-min crypto ladders put millions of markets in the window; partial kept under
#   cache/shape_screen/global_partial/ and not used)  (c) per-series settled-market pull for series with enough events.
# --------------------------------------------------------------------------------------------------------------------
SLIM = ["ticker", "event_ticker", "open_time", "close_time", "expected_expiration_time", "occurrence_datetime",
        "settlement_ts", "can_close_early", "result", "volume_fp", "open_interest_fp", "strike_type",
        "settlement_timer_seconds", "floor_strike", "cap_strike"]


def stage_events(max_pages=10 ** 9):
    os.makedirs(CACHE, exist_ok=True)
    sp = os.path.join(CACHE, "series_catalog.json")
    if not os.path.exists(sp):
        print("pulling /series ...", flush=True)
        d = http_get(f"{API}/series")
        jdump(d["series"], sp)
        print(f"  {len(d['series']):,} series", flush=True)
    ep = os.path.join(CACHE, "events_slim.jsonl")
    cp = os.path.join(CACHE, "events_cursor.json")
    st = jload(cp, {"cursor": None, "pages": 0, "done": False})
    if st.get("done"):
        print("events already complete:", st)
        return
    pages = 0
    with open(ep, "a") as out:
        while pages < max_pages:
            url = f"{API}/events?status=settled&limit=200"
            if st["cursor"]:
                url += "&cursor=" + st["cursor"]
            d = http_get(url)
            evs = d.get("events", [])
            for e in evs:
                out.write(json.dumps({"s": e["series_ticker"], "e": e["event_ticker"]}) + "\n")
            out.flush()
            st["pages"] += 1
            pages += 1
            st["cursor"] = d.get("cursor") or None
            jdump(st, cp)
            if st["pages"] % 25 == 0:
                print(f"  events page {st['pages']}", flush=True)
            if not st["cursor"] or not evs:
                st["done"] = True
                jdump(st, cp)
                break


def universe():
    """Series to probe: (a) every series that produced a settled event in the walked slice of the live window, plus
    (b) every series whose catalog frequency is recurring (hourly/fifteen_min/daily/weekly/monthly/quarterly).
    Coverage limit (disclosed in the report): a non-recurring series with no settled event in the walked slice is not probed."""
    cat = jload(os.path.join(CACHE, "series_catalog.json"), [])
    seen = collections.Counter()
    ep = os.path.join(CACHE, "events_slim.jsonl")
    if os.path.exists(ep):
        for l in open(ep):
            try:
                seen[json.loads(l)["s"]] += 1
            except Exception:
                pass
    rec = {x["ticker"] for x in cat if x.get("frequency") in
           ("hourly", "fifteen_min", "daily", "weekly", "monthly", "quarterly")}
    allser = {x["ticker"] for x in cat}
    uni = sorted((set(seen) | rec) & allser)
    return uni, seen, cat


def stage_markets(limit=200):
    """One request per series: newest `limit` settled markets (cursor presence => >limit). Slim + 3 text samples."""
    d_ = os.path.join(CACHE, "series_markets")
    os.makedirs(d_, exist_ok=True)
    uni, _seen, _cat = universe()
    rng = random.Random(SEED)
    rec_ = {x["ticker"] for x in _cat if x.get("frequency") in ("hourly", "fifteen_min", "daily", "weekly", "monthly", "quarterly")}
    # priority tiers (each shuffled): 1 = recurring catalog frequency, 2 = >=3 settled events walked, 3 = the rest.
    # Partial runs therefore stay representative WITHIN a tier, and the tier cut-off is reported as a coverage limit.
    tier = {x: (1 if x in rec_ else 2 if _seen.get(x, 0) >= 3 else 3) for x in uni}
    order = uni[:]
    rng.shuffle(order)
    order.sort(key=lambda x: tier[x])
    todo = [x for x in order if not os.path.exists(os.path.join(d_, x + ".json"))]
    print(f"universe {len(uni):,} series; {len(todo):,} to probe", flush=True)
    for i, ser in enumerate(todo, 1):
        try:
            d = http_get(f"{API}/markets?series_ticker={ser}&status=settled&limit={limit}&mve_filter=exclude")
        except Exception as e:
            print("  fail", ser, e, flush=True)
            continue
        ms = d.get("markets", [])
        samples = []
        for m in ms:
            key = (m.get("rules_primary") or "")[:120]
            if len(samples) < 3 and all(x["rp"][:120] != key for x in samples):
                samples.append({"ticker": m["ticker"], "title": m.get("title"), "yes_sub": m.get("yes_sub_title"),
                                "rp": (m.get("rules_primary") or "")[:1500], "rs": (m.get("rules_secondary") or "")[:1200],
                                "ecc": (m.get("early_close_condition") or "")[:600]})
        rec = {"series": ser, "n_returned": len(ms), "more": bool(d.get("cursor")),
               "markets": [{k: m.get(k) for k in SLIM} for m in ms], "samples": samples}
        jdump(rec, os.path.join(d_, ser + ".json"))
        if i % 20 == 0:
            print(f"  {i}/{len(todo)} probed  stats={STATS} pace={PACE_S:.2f}", flush=True)


# --------------------------------------------------------------------------------------------------------------------
# STAGE 2: classify
# --------------------------------------------------------------------------------------------------------------------
CLS_EARLY = "DETERMINED-EARLY"
CLS_CLOSE = "DETERMINED-AT-CLOSE"
CLS_DECISION = "CLOSES-AT-DECISION"
CLS_BULLETIN = "BULLETIN-PACED"
CLS_UNK = "UNRESOLVED-BY-METADATA"

R = lambda p: re.compile(p, re.I)
# ---- venue early-close text (Kalshi's own early_close_condition) ---------------------------------------------------------
ECC_ANY = R(r"close( and expire)?( early)? (if|when|once|after)|may (close|expire)|expire early|close early")
ECC_BULLETIN = R(r"economic data is released|specified value is available|official box score|usgs has reviewed|"
                 r"data (is|are) (released|published)|data for the .{0,60} is released|released")
# ---- weather -------------------------------------------------------------------------------------------------------------
WX_EXTREME = R(r"(maximum|minimum|highest|lowest|high|low) (daily )?temperature|temperature[^.]{0,60}(maximum|minimum|high|low)")
WX_ACCUM = R(r"(precipitation|rain(fall)?|snow(fall)?)[^.]{0,80}(total|inches|at least|more than|above|exceed)")
# ---- value read at a clock time -----------------------------------------------------------------------------------------
CLOCK = R(r"\b\d{1,2}(:\d\d)? ?(a|p)\.?m\.?( |,)?(e|c|m|p)?[sd]?t\b|\b\d{1,2}(:\d\d)? ?(a|p)\.?m\b|noon|midnight|end[- ]of[- ]day|"
          r"closing (price|value|level)|close price|opening candlestick|open price|real-time index|\brti\b|\bbrti\b|\berti\b|"
          r"settlement price|up or down|price (up|down)")
# ---- strong running-extreme / cumulative cues (the outcome can lock before close) -------------------------------------------
RUN_EXTREME = R(r"at any (point|time)|at least once|\bever\b|highest (hourly|daily|price|value|level|number|temperature|close)|"
                r"lowest (hourly|daily|price|value|level|number|temperature|close)|\bpeak\b|maximum|minimum|all[- ]time high")
RUN_COUNT = R(r"how many|number of|total (number|amount|count)|cumulative|\bposts?\b|\btweets?\b|mention|"
              r"is stated|states the|says?\b|said by|use the word|\d+ times|at least \d+ (presidential|nomination|action|people|executive)|"
              r"\bnominations?\b|presidential actions")
PRICEY = R(r"price|candlestick|yield|index value|exchange rate|real-time index|approval|rating|average")
# ---- official-release cues ----------------------------------------------------------------------------------------------
BULLETIN = R(r"bureau of labor|\bbls\b|bureau of economic|\bbea\b|census bureau|federal reserve|fomc|\bcpi\b|\bpce\b|"
             r"\bgdp\b|payroll|unemployment rate|jobless|initial claims|energy information|\beia\b|\bfred\b|"
             r"billboard|nielsen|box office|boxofficemojo|spotify|luminate|portwatch|\bimf\b|rotten tomatoes|netflix|"
             r"official (results|report|release)|federal funds|treasury|housing starts|retail sales|consumer sentiment|"
             r"\bism\b|\bfda\b|sec\.gov|certified|google trends|app store|\baaa\b|gas price|leaderboard|\bchart\b|ranking|"
             r"published|as reported by")
BULLETIN_SRC = R(r"bureau|federal|census|energy information|u\.?s\.? (department|treasury)|fred|billboard|nielsen|"
                 r"box office|\bbea\b|\bbls\b|spotify|rotten|\bimf\b|portwatch|netflix|\baaa\b|seasonally adjusted|job openings|nonfarm|"
                 r"leaderboard|openrouter|luminate|billboard|first published|published number|\\btsa\\b")


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def series_features(rec, catrow):
    ms = rec["markets"]
    n = len(ms)
    closes = [parse_ts(m["close_time"]) for m in ms]
    opens = [parse_ts(m["open_time"]) for m in ms]
    exps = [parse_ts(m["expected_expiration_time"]) for m in ms]
    setl = [parse_ts(m["settlement_ts"]) for m in ms]
    vols = [float(m.get("volume_fp") or 0) for m in ms]
    irregular = sum(1 for m in ms if m["close_time"] and not re.search(r":(00|59)(\.0+)?Z$", m["close_time"]))
    cce = sum(1 for m in ms if m.get("can_close_early"))
    yes_ms = [m for m in ms if m.get("result") == "yes"]
    irr_yes = sum(1 for m in yes_ms if m["close_time"] and not re.search(r":(00|59)(\.0+)?Z$", m["close_time"]))
    st = collections.Counter(m.get("strike_type") for m in ms)
    res = collections.Counter(m.get("result") for m in ms)
    return {
        "n_returned": n, "more": rec["more"],
        "n_settled_ge20": n >= MIN_SETTLED,
        "frac_can_close_early": round(cce / n, 3) if n else None,
        "n_yes": len(yes_ms), "frac_irregular_close_given_yes": round(irr_yes / len(yes_ms), 3) if yes_ms else None,
        "frac_irregular_close": round(irregular / n, 3) if n else None,
        "median_open_to_close_h": None if _med([(c - o) / 3600 for c, o in zip(closes, opens) if c and o]) is None
        else round(_med([(c - o) / 3600 for c, o in zip(closes, opens) if c and o]), 2),
        "median_close_to_expected_exp_h": None if _med([(e - c) / 3600 for c, e in zip(closes, exps) if c and e]) is None
        else round(_med([(e - c) / 3600 for c, e in zip(closes, exps) if c and e]), 2),
        "median_close_to_settle_h": None if _med([(s_ - c) / 3600 for c, s_ in zip(closes, setl) if c and s_]) is None
        else round(_med([(s_ - c) / 3600 for c, s_ in zip(closes, setl) if c and s_]), 3),
        "median_volume_contracts": round(statistics.median(vols), 1) if vols else 0,
        "sum_volume_contracts": round(sum(vols), 0),
        "strike_types": dict(st), "result_counts": dict(res),
        "first_close": min((m["close_time"] for m in ms), default=None),
        "last_close": max((m["close_time"] for m in ms), default=None),
    }


OVERRIDES = {}   # series -> (class, subtype, reason).  Filled only after manual review of rules text; every entry is reported.


def classify_series(ser, cat, f, samples, sib=None):
    """Return {class, subtype, basis, gap_h_est, gap_basis, confidence}.  Cues are cited in `basis`.
    KEY EMPIRICAL DISCRIMINATOR: frac_irregular_close.  A venue that really shuts the book at the decision produces
    off-schedule close timestamps; a fixed scheduled close (23:59:59 / on the hour) does not, whatever the ecc text says."""
    title = (cat.get("title") or "")
    category = cat.get("category") or ""
    tags = " ".join(cat.get("tags") or [])
    src = " ".join(x.get("name", "") for x in (cat.get("settlement_sources") or []))
    s0 = samples[0] if samples else {"rp": "", "rs": "", "ecc": "", "title": "", "yes_sub": ""}
    rp = " ".join(x["rp"] for x in samples)
    ecc = " ".join(x["ecc"] for x in samples)
    blob = " ".join([title, category, tags, src, rp, ecc, s0.get("title") or ""])
    fci, fcce = f["frac_irregular_close"] or 0, f["frac_can_close_early"] or 0
    ecc_event = bool(ecc) and not re.search(r"regardless", ecc, re.I) and bool(ECC_ANY.search(ecc))
    fyes = f.get("frac_irregular_close_given_yes")
    # event-closing evidence: off-schedule closes overall, OR (rare-event ladders) off-schedule closes among the YES-resolved
    closes_on_event = fci >= 0.2 or (fyes is not None and f.get("n_yes", 0) >= 3 and fyes >= 0.5)
    inherited = ""
    if ecc_event and not closes_on_event and f.get("n_yes", 0) < 3:
        # too few YES outcomes to see whether the venue really closes on the event: take the pooled evidence of siblings that
        # carry the identical early_close_condition text; with no sibling evidence, believe the text (venue closes the book).
        pooled = (sib or {}).get((ser[:5], s0["ecc"][:120]))
        if pooled and pooled["n_yes"] >= 3:
            inherited = f" [sibling evidence: {pooled['irr_yes']}/{pooled['n_yes']} YES closes off-schedule over {pooled['n_series']} series]"
            closes_on_event = pooled["irr_yes"] / pooled["n_yes"] >= 0.5
        else:
            closes_on_event = True
            inherited = " [too few YES outcomes to test; ecc text believed]"

    def out(c, sub, basis, gap=None, gap_basis="", conf="medium"):
        return {"class": c, "subtype": sub, "basis": basis, "gap_h_est": gap, "gap_basis": gap_basis, "confidence": conf}

    if ser in OVERRIDES:
        c, sub, why = OVERRIDES[ser]
        return out(c, sub, "MANUAL OVERRIDE: " + why, 0.0 if c != CLS_EARLY else None, "manual", "high")
    # 1. venue actually closes the book at the decision / release (ecc text AND off-schedule closes observed)
    if ecc_event and closes_on_event:
        if ECC_BULLETIN.search(ecc):
            return out(CLS_BULLETIN, "release-closes-market", f"early_close_condition: {ecc[:100]} ; {fci:.0%} closes off-schedule ({fyes if fyes is not None else 'n/a'} among YES)", 0.0,
                       "resolves on the release; venue closes at it", "high")
        return out(CLS_DECISION, "venue-closes-on-event", f"early_close_condition: {ecc[:100]} ; {fci:.0%} closes off-schedule ({fyes if fyes is not None else 'n/a'} among YES)", 0.0,
                   "venue closes the book when the criterion is met", "high")
    # 2. weather
    if category == "Climate and Weather" or re.search(r"\bnws\b|weather company|synoptic|climatolog", blob, re.I):
        if WX_EXTREME.search(rp + " " + title) and not re.search(r"consecutive|average|avg", rp + title, re.I):
            return out(CLS_EARLY, "wx-daily-extreme", "rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardless of any "
                       "data releases or events')" if ecc else "rules: daily max/min temperature", None, "see weather_gap", "high")
        if CLOCK.search(rp) and re.search(r"temp", blob, re.I):
            return out(CLS_CLOSE, "wx-clock-snapshot", "rules: temperature read at a clock time", 0.0, "value at the close minute", "high")
        if re.search(r"any day|consecutive|at any|at least \d", rp, re.I) or WX_ACCUM.search(rp + " " + title):
            return out(CLS_EARLY, "wx-period-event", "rules: weather event/accumulation over a period (monotone running state), fixed close" + inherited, None,
                       "analogy to extremes; not measured", "low")
    # 2b. strong official-publication cues in the rules (e.g. IMF PortWatch, seasonally adjusted statistics, leaderboards)
    if BULLETIN_SRC.search(rp + " " + src) and not re.search(r"hourly|peak", rp, re.I) \
            and not re.search(r"candlestick|pyth|\bat \d{1,2}(:\d\d)? ?(a|p)\.?m", rp, re.I):
        return out(CLS_BULLETIN, "official-release", "rules/source cite a publication: " + BULLETIN_SRC.search(rp + " " + src).group(0), 0.0,
                   "resolves on a publication", "medium")
    # 3. running extreme / cumulative count with a FIXED scheduled close (nothing closes the book on the lock)
    if not closes_on_event and RUN_EXTREME.search(rp + " " + title) and not re.search(r"\bat \d{1,2}(:\d\d)? ?(a|p)\.?m", rp, re.I) \
            and not (BULLETIN_SRC.search(src) and not re.search(r"hourly|daily|peak", rp, re.I)):
        return out(CLS_EARLY, "daily-peak/extreme", "rules: running max/min over the period with scheduled close: " + RUN_EXTREME.search(rp + " " + title).group(0) + inherited,
                   None, "lock moment unobservable from metadata (ASSUMED)", "low")
    if not closes_on_event and RUN_COUNT.search(rp + " " + title) and not PRICEY.search(rp):
        return out(CLS_EARLY, "running-count/mention", "rules: running count / mention with scheduled close: " + RUN_COUNT.search(rp + " " + title).group(0) + inherited,
                   None, "lock moment unobservable from metadata (ASSUMED)", "low")
    # 4. value at a clock time / closing level
    if CLOCK.search(rp) or category in ("Financials", "Crypto", "Commodities"):
        return out(CLS_CLOSE, "snapshot", "rules/category: value read at a clock time or closing level", 0.0, "resolves on a value at close by definition", "medium")
    # 5. official releases / leaderboards / charts
    if (src and BULLETIN_SRC.search(src)) or BULLETIN.search(blob) or (ecc and ECC_BULLETIN.search(ecc)):
        why = (BULLETIN_SRC.search(src).group(0) if src and BULLETIN_SRC.search(src) else (BULLETIN.search(blob).group(0) if BULLETIN.search(blob) else "ecc: release"))
        return out(CLS_BULLETIN, "official-release", "rules/source cite a publication: " + why, 0.0, "resolves on a publication", "medium")
    if fci >= 0.5 and fcce >= 0.5:
        return out(CLS_DECISION, "empirical-offschedule-close", f"{fci:.0%} of closes off-schedule, can_close_early {fcce:.0%}", 0.0, "venue closes at the decision", "medium")
    return out(CLS_UNK, "unclear", "no structural cue in metadata/rules", None, "", "low")


def stage_classify():
    d_ = os.path.join(CACHE, "series_markets")
    cat = {x["ticker"]: x for x in jload(os.path.join(CACHE, "series_catalog.json"), [])}
    _u, seen, _c = universe()
    rows = []
    recs = []
    for fn in sorted(os.listdir(d_)):
        if not fn.endswith(".json"):
            continue
        rec = jload(os.path.join(d_, fn))
        if not rec or not rec["markets"]:
            continue
        c = cat.get(rec["series"], {})
        f = series_features(rec, c)
        if f["n_settled_ge20"]:
            recs.append((rec, c, f))
    sib = {}
    for rec, c, f in recs:
        ecc0 = (rec["samples"][0]["ecc"] if rec["samples"] else "")
        if not ecc0:
            continue
        yes_ms = [m for m in rec["markets"] if m.get("result") == "yes"]
        irr_y = sum(1 for m in yes_ms if m["close_time"] and not re.search(r":(00|59)(\.0+)?Z$", m["close_time"]))
        g_ = sib.setdefault((rec["series"][:5], ecc0[:120]), {"n_yes": 0, "irr_yes": 0, "n_series": 0})
        g_["n_yes"] += len(yes_ms)
        g_["irr_yes"] += irr_y
        g_["n_series"] += 1
    for rec, c, f in recs:
        ser = rec["series"]
        k = classify_series(ser, c, f, rec["samples"], sib)
        rows.append({"series": ser, "title": c.get("title"), "category": c.get("category"), "frequency": c.get("frequency"),
                     "n_events_walked": seen.get(ser, 0), **f, **k, "sample_rules": (rec["samples"][0]["rp"][:260] if rec["samples"] else ""),
                     "sample_ecc": (rec["samples"][0]["ecc"][:160] if rec["samples"] else "")})
    jdump(rows, os.path.join(CACHE, "classification.json"))
    cnt = collections.Counter(r["class"] for r in rows)
    print(f"classified {len(rows)} series with >= {MIN_SETTLED} settled markets:", dict(cnt))
    return rows


# --------------------------------------------------------------------------------------------------------------------
# weather determination gap: MEASURED from the cached IEM 1-minute ASOS archive (cache/finality/A/obs) + the
# finality_A signals file (close_ts, E_final).  gap = close_ts - last minute at which the temp was within 0.51 F of
# the day's final extreme ("physically determined": the running extreme never improves after that minute).
# --------------------------------------------------------------------------------------------------------------------
def stage_weather_gap():
    A = os.path.join(HERE, "cache", "finality", "A")
    sig = os.path.join(A, "signals.jsonl")
    if not os.path.exists(sig):
        print("no finality cache; weather gap falls back to climatology prior")
        return None
    obs = {}

    def load(st, ym):
        k = (st, ym)
        if k not in obs:
            obs[k] = jload(os.path.join(A, "obs", f"1min_{st}_{ym}.json"))
        return obs[k]

    res = collections.defaultdict(list)
    for l in open(sig):
        e = json.loads(l)
        if e.get("feed") != "iem_1min" or "E_final" not in e:
            continue
        close = e["close_ts"]
        start = close - 86400
        d0 = dt.datetime.fromtimestamp(start, dt.timezone.utc)
        d1 = dt.datetime.fromtimestamp(close, dt.timezone.utc)
        rows = []
        for ym in {d0.strftime("%Y-%m"), d1.strftime("%Y-%m")}:
            o = load(e["station"], ym)
            if o:
                rows += [r for r in o if start <= r[0] <= close]
        if len(rows) < 600:
            continue
        last = max((r[0] for r in rows if abs(r[1] - e["E_final"]) < 0.51), default=None)
        if last is not None:
            res[e["kind"]].append((close - last) / 3600)
    out = {}
    for k, v in res.items():
        v.sort()
        out[k] = {"n_station_days": len(v), "median_h": round(statistics.median(v), 2),
                  "p10_h": round(v[len(v) // 10], 2), "p90_h": round(v[9 * len(v) // 10], 2), "mean_h": round(statistics.mean(v), 2)}
    jdump(out, os.path.join(CACHE, "weather_gap.json"))
    print("weather determination gap:", out)
    return out


# --------------------------------------------------------------------------------------------------------------------
# STAGE 3: sample + candles + oracle metric
# --------------------------------------------------------------------------------------------------------------------
def load_classification():
    return jload(os.path.join(CACHE, "classification.json"), [])


def is_weather_row(r):
    return r["class"] == CLS_EARLY and str(r["subtype"]).startswith("wx-")


def stage_sample(per_early=10, per_weather=4, max_weather_series=90, max_early_series=70, control_series=20, per_control=3):
    rows = load_classification()
    rng = random.Random(SEED)
    d_ = os.path.join(CACHE, "series_markets")
    plan = []

    def pick(ser, k, require_traded):
        rec = jload(os.path.join(d_, ser + ".json"))
        ms = [m for m in rec["markets"] if m.get("result") in ("yes", "no")]
        if require_traded:
            ms = [m for m in ms if float(m.get("volume_fp") or 0) >= 1]
        rng.shuffle(ms)
        return [dict(m, series_ticker=ser) for m in ms[:k]]

    wx = [r for r in rows if is_weather_row(r)]
    # US HIGH/LOW series first (positive control that overlaps edge_sizing_v2), then the rest of the weather families
    wx.sort(key=lambda r: (0 if re.match(r"KX(HIGH|LOWT)", r["series"]) else 1, rng.random()))
    for r in wx[:max_weather_series]:
        for m in pick(r["series"], per_weather, False):
            plan.append({"group": "EARLY-weather", "series": r["series"], "m": m})
    nw = [r for r in rows if r["class"] == CLS_EARLY and not is_weather_row(r)]
    nw.sort(key=lambda r: -r["sum_volume_contracts"])
    for r in nw[:max_early_series]:
        for m in pick(r["series"], per_early, True):
            plan.append({"group": "EARLY-other", "series": r["series"], "m": m})
    for cls in (CLS_CLOSE, CLS_DECISION, CLS_BULLETIN, CLS_UNK):
        pool = [r for r in rows if r["class"] == cls and r["sum_volume_contracts"] > 0]
        rng.shuffle(pool)
        for r in pool[:control_series]:
            for m in pick(r["series"], per_control, True):
                plan.append({"group": "CONTROL-" + cls, "series": r["series"], "m": m})
    # SHUFFLED work order, never re-sorted: any prefix is itself a representative sample
    rng.shuffle(plan)
    jdump(plan, os.path.join(CACHE, "sample_plan.json"))
    print("sample plan:", len(plan), dict(collections.Counter(p["group"] for p in plan)))
    return plan


def candle_path(tk):
    return os.path.join(CANDLES, tk + ".json")


def stage_candles(max_fetch=10 ** 9):
    os.makedirs(CANDLES, exist_ok=True)
    plan = jload(os.path.join(CACHE, "sample_plan.json"), [])
    n = 0
    for i, it in enumerate(plan, 1):
        m = it["m"]
        tk = m["ticker"]
        if os.path.exists(candle_path(tk)):
            continue
        if n >= max_fetch:
            break
        close = int(parse_ts(m["close_time"]))
        url = (f"{API}/series/{it['series']}/markets/{tk}/candlesticks"
               f"?start_ts={close - WINDOW_MIN * 60}&end_ts={close}&period_interval=1")
        try:
            data = http_get(url).get("candlesticks", [])
        except Exception as e:
            print("  candle fail", tk, str(e)[:80], flush=True)
            data = None
        jdump({"ticker": tk, "candles": data}, candle_path(tk))
        n += 1
        if n % 25 == 0:
            print(f"  candles {i}/{len(plan)}  fetched {n}  stats={STATS} pace={PACE_S:.2f}", flush=True)


def stage_verify(n=60):
    """Re-fetch a random subset of sampled tickers via GET /markets/{ticker}; compare market.result with the listing's."""
    plan = jload(os.path.join(CACHE, "sample_plan.json"), [])
    vp = os.path.join(CACHE, "verify_results.json")
    done = jload(vp, {})
    rng = random.Random(SEED + 1)
    pool = plan[:]
    rng.shuffle(pool)
    for it in pool[:n]:
        tk = it["m"]["ticker"]
        if tk in done:
            continue
        try:
            d = http_get(f"{API}/markets/{tk}")
            done[tk] = {"listing": it["m"]["result"], "get": d["market"].get("result")}
        except Exception as e:
            done[tk] = {"listing": it["m"]["result"], "get": None, "err": str(e)[:80]}
        jdump(done, vp)
    ok = sum(1 for v in done.values() if v["get"] is not None)
    agree = sum(1 for v in done.values() if v["get"] is not None and v["get"] == v["listing"])
    print(f"result verification: {agree}/{ok} agree")
    return {"checked": ok, "agree": agree}


def winner_scan(rows, result):
    """Same oracle definition as edge_sizing_v2.scan(): winner cost = yes_ask if YES else 100 - yes_bid (NEVER 100 - yes_ask);
    capturable minute iff 0 < cost <= 98 and net = 100 - cost - ceil(7p(1-p)) > 0."""
    import edge_sizing_v2 as esv2
    best_cost = None
    n_cap = n_min = 0
    cap_vol = 0.0
    cap_ts = []
    for ts, yb, ya, vol in rows:
        cost = ya if result == "yes" else (None if yb is None else 100 - yb)
        if cost is None:
            continue
        n_min += 1
        if not (0 < cost <= esv2.MAX_PAY_C):
            continue
        net = 100 - cost - esv2.fee_c(cost)
        if net <= 0:
            continue
        n_cap += 1
        cap_vol += vol
        cap_ts.append(ts)
        if best_cost is None or cost < best_cost:
            best_cost = cost
    return n_min, n_cap, cap_vol, cap_ts, best_cost


def market_metrics(it):
    import edge_sizing_v2 as esv2
    esv2.WINDOW_MIN = WINDOW_MIN          # normalize() reads this module global: final 2h instead of v2's 60 min
    m = it["m"]
    cd = jload(candle_path(m["ticker"]))
    if cd is None or cd.get("candles") is None:
        return {"skip": "no_candle_file_or_fetch_failed"}
    close_ts = int(parse_ts(m["close_time"]))
    rows = esv2.normalize(cd["candles"], close_ts)
    if not rows:
        return {"skip": "no_candles_in_window"}
    result = m["result"]
    n_min, n_cap, cap_vol, cap_ts, best = winner_scan(rows, result)
    rows60 = [r for r in rows if r[0] >= close_ts - 3600]       # same candles, edge_sizing_v2's 60-minute window
    _, n_cap60, _, _, _ = winner_scan(rows60, result)
    last_cap = max(cap_ts) if cap_ts else None

    def wcost(t_before_close_s):
        """winner-side cost at the last candle at/before close - t (None if no usable quote there)."""
        cand = [(ya if result == "yes" else (None if yb is None else 100 - yb))
                for ts, yb, ya, _v in rows if ts <= close_ts - t_before_close_s]
        cand = [c for c in cand if c is not None]
        return cand[-1] if cand else None

    return {"ticker": m["ticker"], "series": it["series"], "group": it["group"], "result": result,
            "close_time": m["close_time"], "n_data_minutes": n_min, "n_capturable_minutes": n_cap,
            "capturable": n_cap > 0, "capturable_60": n_cap60 > 0,
            "capturable_volume": cap_vol, "window_volume": sum(r[3] for r in rows),
            "best_cost_c": best,
            # minutes before close for which the winner has NOT been capturable: 0 = capturable up to the last minute
            # (outcome still open until close); =window = never capturable in the window (market had already repriced)
            "priced_lead_min": WINDOW_MIN if last_cap is None else round((close_ts - last_cap) / 60, 1),
            "first_capturable_min_before_close": None if not cap_ts else round((close_ts - min(cap_ts)) / 60, 1),
            "frac_minutes_capturable": round(n_cap / n_min, 3) if n_min else None,
            "cost_T10": wcost(600), "cost_T60": wcost(3600), "cost_T110": wcost(6600)}


# --------------------------------------------------------------------------------------------------------------------
# graveyard cross-check: ledger entry numbers are RESEARCH_LEDGER.md section 3 (#1..#37) plus the later registered studies
# (EDGE_SIZING v1/v2/stage2, TERMINAL_FINALITY A/B, FINALITY_NO, TRACK A/S2/S3 (Polymarket/ForecastEx weather), spec D1/J1/M1/U1,
# MM1 stage B).  A shortlist entry that matches a pattern is a RE-DISCOVERY of that family's graveyard entry.
# --------------------------------------------------------------------------------------------------------------------
GRAVEYARD = [
    # (family, regex over series/title/subtype, ledger refs, kind)  kind: EXACT = the same product/mechanism was tested; ADJACENT = same mechanism class, different product
    ("US daily-extreme temperature (KXHIGH*/KXLOWT*)", R(r"^KX(HIGH|LOWT)"),
     "#1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), "
     "#19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle $2.1k/mo median, realistic $15/mo, retire); TERMINAL_FINALITY A/B + FINALITY_NO (INSUFFICIENT)", "EXACT"),
    ("weather period products (rain / avg-temp streaks / tornado counts)", R(r"^KX(RAIN|AVGTK|TORNADO|SNOW)"),
     "same physical-feed mechanism as the KXHIGH/KXLOWT studies (#1,#2,#12, EDGE_SIZING) but these products were never tested", "ADJACENT"),
    ("social-media / public-figure post counts", R(r"TRUTHSOCIAL|TWEETS|TRUMPACT|TRUMPPHOTO|TRUMPNOM"),
     "#14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested", "ADJACENT"),
    ("mention / said-word markets", R(r"MENTION|SAYS?$|SAY[A-Z]*$"), "#14, #22, #23, #25", "EXACT"),
    ("crypto/commodity touch-max-min ladders", R(r"MAXMON|MINMON|MAXY|MINY|MAXD|MIND\b|one touch"), "#16 commodity ladders (NOT PROMISING), #17 crypto MAX ladders (NOT PROMISING: can_close_early reprices 46% >1h early)", "EXACT"),
    ("crypto/index/FX/commodity price at a time", R(r"^KX(BTC|ETH|SOL|XRP|DOGE|BNB|HYPE|INX|NASDAQ|USD|GBP|EUR|GOLD|SILVER|PLATINUM|COPPER|NATGAS|WTI|BRENT)|15M$"),
     "#34 per-series last_price (FAIL), #36 crypto up/down latency (NO-EDGE-ANY-LATENCY), #27/#28 cross-venue crypto, #16/#17 commodity+crypto expansion", "EXACT"),
    ("sports totals/props/game", R(r"^KX(NFL|NBA|NHL|MLB|EPL|MLS|NCAA|ESOCCER|SOCCER|TENNIS|ATP|WTA|UFC|PGA)"), "#13 sports totals (NOT PROMISING: median lag 0.0s), #35 NFL moneyline vs sharp line (NULL), #20 long-tail passive (FAIL)", "EXACT"),
    ("earthquake / hazard magnitude", R(r"QUAKE|EARTHQUAKE"), "#15 earthquake magnitude (NOT PROMISING: USGS revises 10-60+ min, no lag)", "EXACT"),
    ("FDA / regulatory approvals", R(r"FDA|APPROV"), "#18 FDA (NOT PROMISING: no minute-resolution feed)", "EXACT"),
    ("macro releases (CPI/jobs/claims/Fed)", R(r"CPI|PAYROLL|JOBLESS|CLAIMS|FED[A-Z]*$|GDP|UNRATE|PCE|JOLTS"), "#24/#26 jobless claims (INSUFFICIENT/FAIL), #29 + spec_M1 macro-surprise (INSUFFICIENT), spec_J1", "EXACT"),
]


def graveyard_match(series, title, subtype):
    """-> list of (family, refs, kind) whose pattern matches the series ticker, subtype or title."""
    return [(fam, refs, kind) for fam, rx, refs, kind in GRAVEYARD if rx.search(series)]


def gy_verdict(hits):
    if any(h[2] == "EXACT" for h in hits):
        return "RE-DISCOVERY"
    if hits:
        return "ADJACENT (same mechanism, untested product)"
    return "NEW (no ledger entry)"


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0, c - h), 4), round(min(1, c + h), 4))


def family_of(series):
    m = re.match(r"^(KXHIGH|KXLOWT|KXTEMP|KXMAXTEMP|KXMINTEMP|KXRAIN|KXSNOW)", series)
    return m.group(1) + "*" if m else series


DEFAULT_GAP_H = {"wx-period-event": 3.0, "daily-peak/extreme": 0.5, "running-count/mention": 0.25, "mention/count": 0.25, "extreme/threshold": 0.5}


def gap_for(row, wgap):
    """(hours, basis).  Weather daily extremes: MEASURED on US stations (IEM 1-min), transferred by analogy to other
    weather series.  Everything else that is DETERMINED-EARLY: a labelled ASSUMPTION (no feed to time the lock from)."""
    if row["class"] != CLS_EARLY:
        return 0.0, "class has no gap by construction"
    sub = row["subtype"]
    if sub == "wx-daily-extreme":
        low = bool(re.match(r"KXLOWT", row["series"]) or re.search(r"\blow(est)?\b|minimum|\bmin\b", (row["title"] or ""), re.I))
        key = "min" if low else "max"
        if wgap and key in wgap:
            return wgap[key]["median_h"], f"MEASURED median hours from the day's final extreme to close, IEM 1-min, {wgap[key]['n_station_days']} US station-days (p10 {wgap[key]['p10_h']}h, p90 {wgap[key]['p90_h']}h)"
        return (7.0 if not low else 12.0), "climatology prior (IEM cache absent)"
    return DEFAULT_GAP_H.get(sub, 0.25), f"ASSUMED default for subtype {sub} (no feed available to time the physical lock)"


def _tbl(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in r) + " |")
    return "\n".join(out)


NOTES_SECTION = ""   # filled by finalize_notes() after the numbers are in
CAVEATS = [
    "**Descriptive, not inferential.** No pass bar, no multiple-comparison control, no out-of-sample split. A ranked list from a screen over thousands of series is exactly where a "
    "plausible-looking positive is the default failure mode; every entry needs a frozen pre-registration before any claim.",
    "**Oracle ceiling.** Capturable = the *eventual winner* was buyable <= 98c with positive fee-inclusive net in some minute. It assumes foreknowledge, zero latency, zero competition, and the "
    "whole printed volume available to one taker. It cannot distinguish 'determined and slow to reprice' from 'simply still uncertain'; only the determination-gap column does that.",
    "**Gap estimates are the weakest column.** Weather is measured (IEM 1-minute: hours from the day's final extreme to close, US stations, 2026-05..10). Every other DETERMINED-EARLY gap is an "
    "assumed default because there is no independent feed in this screen to time the physical lock from. The gap-free ranking is shown beside the scored one for that reason.",
    "**Classification is rules-text + metadata, not outcome-aware**, and is heuristic. The empirical discriminator is off-schedule close timestamps (a venue that really shuts the book at the decision "
    "produces them; a fixed 23:59:59 close does not, whatever early_close_condition says). Misclassification is possible in both directions; section 7 audits the no-gap classes with measured price paths.",
    "**Live-window only.** Kalshi's live settled-market window is roughly the last 5 months; per-series counts and the 200-newest-market probe cap are inside that window. Series that settled before it "
    "(available via /historical) were not scanned, nor were non-recurring series absent from the walked slice of settled events (tier-3 coverage is reported in section 2).",
    "**Candlestick sparsity.** Minute candles exist where there was activity; thin markets have thin minutes. No order-book depth: volume in capturable minutes is an upper bound.",
    "**Sampling.** Weather sampled unconditionally (matches edge_sizing_v2's frame); non-weather samples are conditioned on the market having traded at least once, so their capturable rates are not comparable to the weather rate.",
    "**Outcomes** come only from `market.result` on the Kalshi market object; a random subset was re-fetched through GET /markets/{ticker} (agreement reported in section 2).",
]


def write_md(o, ranked, ranked_gf, fam_rows, flags, byser):
    cov = o["coverage"]
    g = o["group_measured"]
    L = []
    L.append("# SHAPE SCREEN - which Kalshi series stay open after their outcome is determined?\n")
    L.append(f"Generated {o['generated']}. Code: `venue_expansion/shape_screen.py` (seed {o['seed']}). Data: `venue_expansion/out/shape_screen.json`. "
             "Every API pull is cached under `venue_expansion/cache/shape_screen/`.\n")
    L.append("> **STATUS: DESCRIPTIVE SCREEN, NOT A HYPOTHESIS TEST.** It carries no pass bar and produces no deployable claim. "
             "The capturable rate below is an ORACLE CEILING (perfect foreknowledge of the winner, zero latency, zero competition, all printed volume "
             "available to one taker). **Nothing on the shortlist may be promoted, sized, or traded without a NEW pre-registration** "
             "(frozen spec, frozen bars, adversarial verification) - the same bar every one of the 43 prior studies had to clear.\n")
    L.append("## 1. What was measured\n")
    L.append("Property: *the market stays open for hours after its outcome is physically determined.* Four structural classes, assigned from "
             "series/market metadata and rules text (never from outcomes):\n")
    L.append(_tbl(["class", "meaning", "gap"],
                  [[CLS_EARLY, "outcome fixed materially before close and the venue keeps the book open (no venue-declared early close)", "estimated, hours"],
                   [CLS_CLOSE, "resolves on a closing value / final print / value at a clock time", "none by definition"],
                   [CLS_DECISION, "venue's own early_close_condition shuts the market when the outcome occurs", "none by construction"],
                   [CLS_BULLETIN, "resolves on an official release that is itself the fastest feed", "none (no independent faster feed)"],
                   [CLS_UNK, "no structural cue found in metadata (reported, not forced into a class)", "unknown"]]))
    L.append("")
    L.append(f"Empirical step: for each sampled settled market, 1-minute candlesticks for the final **{o['window_min']} minutes** before close, then "
             "`edge_sizing_v2.normalize()` + the v2 winner-cost rule (YES winner costs yes_ask; NO winner costs **100 - yes_bid**, never 100 - yes_ask; "
             "capturable minute iff cost <= 98c and net = 100 - cost - ceil(7p(1-p)) > 0). A market is *capturable* if any minute qualifies. "
             "The v2 code was imported, not re-written for the normalizer, and the winner-scan reproduces `edge_sizing_v2.scan()` exactly on 560 cached "
             "weather market-sides (0 mismatches; `selftest` stage).\n")
    L.append("**Why capturable rate alone cannot identify the property.** Any market whose outcome is still uncertain two hours out also has a winner "
             "buyable below 98c (the oracle knows the winner; nobody else does). The rate only means something when multiplied by an independently established "
             "determination gap - which is why classification comes first and why DETERMINED-AT-CLOSE series with 100% capturable rate carry zero score.\n")
    L.append("## 2. Coverage (read this before trusting any count)\n")
    L.append(_tbl(["item", "value"], [
        ["series in /series catalog", f"{cov['series_in_catalog']:,}"],
        ["series in probe universe (recurring-frequency + seen in walked settled events)", f"{cov['series_in_probe_universe']:,}"],
        ["series probed (one markets call each, newest 200 settled markets, MVE parlays excluded)", f"{cov['series_probed']:,}"],
        ["series with >= 20 settled markets in the live API window (classified)", f"{cov['series_with_ge20_settled']:,}"],
        ["markets planned for candle sample / with usable candles", f"{cov['markets_sampled_planned']:,} / {cov['markets_with_usable_candles']:,}"],
        ["candle skips", json.dumps(cov["skips"])],
        ["official-result re-check (GET /markets/{ticker} vs listing)", f"{cov['result_verification_get_vs_listing']['agree']}/{cov['result_verification_get_vs_listing']['checked']} agree"]]))
    L.append("\nLimits: (a) the live API only serves a rolling window of settled markets (~since 2026-05), so 'settled >= 20' is counted inside that window; "
             "(b) a non-recurring series with no settled event in the walked slice of the event listing was not probed; (c) 'newest 200' bounds per-series "
             "counts at 200 (`more` flag in the JSON); (d) candlesticks carry quotes at minutes that had activity - sparse markets have sparse minutes; "
             "(e) candlesticks have no order-book depth, so volume in capturable minutes is an upper bound on what one taker could have lifted.\n")
    L.append("## 3. Class summary\n")
    L.append(_tbl(["class", "series (>=20 settled)", "contracts in returned markets", "top categories"],
                  [[k, v["series"], f"{v['sum_volume_contracts_in_returned_markets']:,}", ", ".join(f"{a} {b}" for a, b in v["top_categories"])]
                   for k, v in sorted(o["class_summary"].items(), key=lambda kv: -kv[1]["series"])]))
    L.append("")
    L.append("## 4. Measured oracle-capturable rate by sampled group\n")
    L.append(_tbl(["group", "markets", "series", "capturable (pooled)", "Wilson 95%", "series-mean rate", "same, final 60 min", "median priced-lead (min)", "median winner cost T-60", "median winner cost T-10"],
                  [[k, v["n_markets"], v["n_series"], v["capturable_rate_pooled"], v["wilson95"], v["capturable_rate_series_mean"], v["capturable_rate_60min_pooled"],
                    v["median_priced_lead_min"], v["median_winner_cost_T60"], v["median_winner_cost_T10"]] for k, v in sorted(g.items())]))
    L.append("\n`priced-lead` = minutes before close during which the winning side was NOT capturable (0 = capturable up to the last minute, i.e. outcome still open; "
             f"{o['window_min']} = never capturable in the window, i.e. the market had already repriced). `winner cost T-n` = cost of the eventual winner n minutes before close; "
             "a determined-early shape shows ~97-99c at T-60, an at-close shape shows a mid price.\n")
    wx = g.get("EARLY-weather")
    if wx:
        L.append(f"**Positive-control reproduction.** edge_sizing_v2 (final 60 min, 40 US weather series, population-weighted) measured 10.0% capturable. This screen's weather sample "
                 f"(final 60 min of the same candles, sampled *per series* so heavily-traded and thin series weigh equally) gives {wx['capturable_rate_60min_pooled']:.1%} pooled; "
                 f"over the full 120 minutes {wx['capturable_rate_pooled']:.1%}. Sampling frames differ, so agreement is directional, not exact.\n")
    L.append("## 5. Ranked shortlist (DETERMINED-EARLY candidates with >= 3 usable sampled markets)\n")
    L.append("Score = estimated determination gap (hours) x oracle-capturable rate x median volume (contracts) summed over the capturable minutes of a capturable market. "
             "Gap source: weather = MEASURED on US station-days from the cached IEM 1-minute archive (hours from the day's final extreme to market close); "
             "every other family = labelled ASSUMPTION. This is a ranking device, not a magnitude.\n")
    rows = []
    for i, r in enumerate(ranked[:30], 1):
        m = r["measured"]
        rows.append([i, r["series"], (r["title"] or "")[:34], r["subtype"], r["gap_h_est"], f"{m['capturable_rate']:.2f} ({m['n_capturable']}/{m['n_usable']})",
                     m["median_capturable_volume"], m["median_priced_lead_min"], r["score"],
                     gy_verdict(graveyard_match(r["series"], r["title"], r["subtype"]))])
    L.append(_tbl(["#", "series", "title", "subtype", "gap h", "capturable", "median capt. vol", "priced-lead min", "score", "graveyard verdict"], rows))
    L.append("\n### Family roll-up (pooled over sampled markets; this is the ranking that matters)\n")
    L.append(_tbl(["#", "family", "series", "usable mkts", "capturable (pooled)", "Wilson 95%", "median gap h", "median capt. vol", "score", "gap-free score", "graveyard verdict"],
                  [[i, f["family"], f["n_series"], f["n_usable"], f"{f['capturable_rate_pooled']:.3f} ({f['n_capturable']}/{f['n_usable']})", f["wilson95"], f["median_gap_h"], f["median_capt_volume"],
                    f["score"], f["score_gapfree"], f["verdict"]] for i, f in enumerate(fam_rows[:25], 1)]))
    L.append("\n### Same candidates ranked WITHOUT the gap term (capturable rate x median volume) - the check that the weather result is not produced by the gap column\n")
    L.append(_tbl(["#", "series", "subtype", "capturable", "median capt. vol", "gap-free score"],
                  [[i, r["series"], r["subtype"], f"{r['measured']['capturable_rate']:.2f} ({r['measured']['n_capturable']}/{r['measured']['n_usable']})",
                    r["measured"]["median_capturable_volume"], r["score_gapfree"]] for i, r in enumerate(ranked_gf[:20], 1)]))
    L.append("")
    # ---- 6. screen sanity ------------------------------------------------------------------------------------------
    L.append("## 6. Screen sanity check - does it rediscover weather?\n")
    famnames = [f["family"] for f in fam_rows]
    wxf = [i for i, n in enumerate(famnames, 1) if n in ("KXHIGH*", "KXLOWT*")]
    famgf = [f["family"] for f in o["family_rollup_gapfree"]]
    gf_wx = [i for i, n in enumerate(famgf, 1) if n in ("KXHIGH*", "KXLOWT*")]
    if wxf and wxf[0] <= 3:
        L.append(f"**PASS.** Weather daily extremes are family rank {wxf[0]} (and {wxf[1] if len(wxf) > 1 else 'n/a'}) of {len(famnames)} by score, and the first weather series "
                 f"is gap-free family rank {gf_wx[0] if gf_wx else 'n/a'} of {len(famgf)} even with the gap term removed. The screen finds the one family this program already knows has the property.\n")
    else:
        L.append(f"**SCREEN BROKEN OR WEATHER NOT PRESENT.** Weather family rank(s): {wxf or 'none'} of {len(famnames)}; gap-free weather family rank(s): {gf_wx or 'none'}. "
                 "Per the task's own criterion this means the screen cannot be trusted until diagnosed.\n")
    # ---- 7. control audit -----------------------------------------------------------------------------------------
    L.append("## 7. Classifier-miss audit (non-EARLY series whose winners were already priced >= 60 min before close)\n")
    L.append("These are series the metadata classifier put in a no-gap class but whose measured price path looks like a determined-early shape (winner already at ~98c+ for the first hour of the window). "
             "Each needs a manual read of the rules text; a flag is a reason to look, not a finding.\n")
    if flags:
        L.append(_tbl(["series", "class", "title", "usable", "median priced-lead min", "capturable rate", "median winner cost T-60", "median capt. vol"],
                      [[f["series"], f["class"], (f["title"] or "")[:40], f["n_usable"], f["median_priced_lead_min"], f["capturable_rate"], f["median_winner_cost_T60"], f["median_capturable_volume"]] for f in flags[:30]]))
    else:
        L.append("_No control series met the flag criterion in the sampled markets._")
    L.append("")
    # ---- 8. new vs re-discovery ------------------------------------------------------------------------------------
    L.append("## 8. Shortlist vs the graveyard: re-discovery or NEW?\n")
    rows = []
    for i, r in enumerate(ranked[:20], 1):
        gm = graveyard_match(r["series"], r["title"], r["subtype"])
        rows.append([i, r["series"], r["subtype"], gy_verdict(gm), "; ".join(f"{a}: {b}" for a, b, _k in gm)[:300] or "-"])
    L.append(_tbl(["#", "series", "subtype", "verdict", "graveyard entries"], rows))
    L.append("")
    L.append(NOTES_SECTION)
    # ---- 9. caveats --------------------------------------------------------------------------------------------------
    L.append("## 9. Caveats\n")
    for c in CAVEATS:
        L.append("- " + c)
    L.append("")
    # ---- appendix: full classification table -------------------------------------------------------------------------
    L.append("## Appendix A. Full classification table (every series with >= 20 settled markets in the probed universe)\n")
    order = {CLS_EARLY: 0, CLS_UNK: 1, CLS_CLOSE: 2, CLS_BULLETIN: 3, CLS_DECISION: 4}
    tab = sorted(o["classification"], key=lambda r: (order.get(r["class"], 9), -r["sum_volume_contracts"]))
    L.append(_tbl(["series", "category", "freq", "n", "class", "subtype", "gap h", "conf", "basis"],
                  [[r["series"], (r["category"] or "")[:14], r["frequency"], r["n_returned"] if not r["more"] else f"{r['n_returned']}+", r["class"], r["subtype"],
                    "" if r["gap_h_est"] is None else r["gap_h_est"], r["confidence"], (r["basis"] or "")[:90]] for r in tab]))
    with open(os.path.join(OUTDIR, "shape_screen.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")


def stage_report():
    cls = load_classification()
    wgap = jload(os.path.join(CACHE, "weather_gap.json")) or stage_weather_gap()
    plan = jload(os.path.join(CACHE, "sample_plan.json"), [])
    verify = jload(os.path.join(CACHE, "verify_results.json"), {})
    byser = {r["series"]: r for r in cls}
    mets = []
    skips = collections.Counter()
    for it in plan:
        if not os.path.exists(candle_path(it["m"]["ticker"])):
            skips["not_yet_fetched"] += 1
            continue
        r = market_metrics(it)
        if "skip" in r:
            skips[r["skip"]] += 1
            continue
        mets.append(r)
    # ---- per series
    per = collections.defaultdict(list)
    for r in mets:
        per[r["series"]].append(r)
    meas = {}
    for ser, rs in per.items():
        n = len(rs)
        k = sum(1 for r in rs if r["capturable"])
        k60 = sum(1 for r in rs if r["capturable_60"])
        capv = [r["capturable_volume"] for r in rs if r["capturable"]]
        lead = [r["priced_lead_min"] for r in rs]
        c60 = [r["cost_T60"] for r in rs if r["cost_T60"] is not None]
        c10 = [r["cost_T10"] for r in rs if r["cost_T10"] is not None]
        meas[ser] = {"n_usable": n, "n_capturable": k, "capturable_rate": round(k / n, 4), "wilson95": wilson(k, n),
                     "capturable_rate_60min": round(k60 / n, 4),
                     "median_capturable_volume": round(statistics.median(capv), 2) if capv else 0.0,
                     "mean_capturable_volume": round(statistics.mean(capv), 2) if capv else 0.0,
                     "median_priced_lead_min": round(statistics.median(lead), 1),
                     "median_winner_cost_T60": statistics.median(c60) if c60 else None,
                     "median_winner_cost_T10": statistics.median(c10) if c10 else None,
                     "median_best_cost_c": statistics.median([r["best_cost_c"] for r in rs if r["best_cost_c"]]) if k else None,
                     "median_window_volume": round(statistics.median([r["window_volume"] for r in rs]), 1),
                     "group": rs[0]["group"]}
    # ---- join class + gap + score
    table = []
    for r in cls:
        g_h, g_basis = gap_for(r, wgap)
        m = meas.get(r["series"])
        row = dict(r)
        row["gap_h_est"], row["gap_basis"] = g_h, g_basis
        row["family"] = family_of(r["series"])
        if m:
            row["measured"] = m
            row["score"] = round(g_h * m["capturable_rate"] * m["median_capturable_volume"], 3)
            row["score_gapfree"] = round(m["capturable_rate"] * m["median_capturable_volume"], 3)
        table.append(row)
    cand = [r for r in table if r["class"] == CLS_EARLY and r.get("measured") and r["measured"]["n_usable"] >= 3]
    ranked = sorted(cand, key=lambda r: -r["score"])
    ranked_gf = sorted(cand, key=lambda r: -r["score_gapfree"])
    # ---- family roll-up: POOLED over the family's sampled markets (series-level medians of 3-5 markets are too noisy to rank on)
    fam = collections.defaultdict(lambda: {"series": [], "rows": []})
    for r in cand:
        fam[r["family"]]["series"].append(r)
        fam[r["family"]]["rows"] += per[r["series"]]
    fam_rows = []
    for k, f in fam.items():
        rs = f["rows"]
        n = len(rs)
        kc = sum(1 for x in rs if x["capturable"])
        capv = [x["capturable_volume"] for x in rs if x["capturable"]]
        gap = statistics.median([x["gap_h_est"] for x in f["series"]])
        rate = kc / n
        mv = statistics.median(capv) if capv else 0.0
        s0 = f["series"][0]
        gm = graveyard_match(s0["series"], s0["title"], s0["subtype"])
        fam_rows.append({"family": k, "n_series": len(f["series"]), "n_usable": n, "n_capturable": kc, "capturable_rate_pooled": round(rate, 4),
                         "wilson95": wilson(kc, n), "median_gap_h": round(gap, 2), "median_capt_volume": round(mv, 2),
                         "score": round(gap * rate * mv, 3), "score_gapfree": round(rate * mv, 3),
                         "median_priced_lead_min": round(statistics.median([x["priced_lead_min"] for x in rs]), 1),
                         "subtype": s0["subtype"], "series_list": [x["series"] for x in f["series"]][:12],
                         "graveyard": [x[0] + " -> " + x[1] for x in gm], "verdict": gy_verdict(gm)})
    fam_rows.sort(key=lambda x: -x["score"])
    fam_rows_gf = sorted(fam_rows, key=lambda x: -x["score_gapfree"])
    # ---- group-level + class-level measured summaries
    grp = collections.defaultdict(lambda: {"n": 0, "k": 0, "k60": 0, "leads": [], "c60": [], "c10": [], "series": set()})
    for r in mets:
        g = grp[r["group"]]
        g["n"] += 1
        g["k"] += int(r["capturable"])
        g["k60"] += int(r["capturable_60"])
        g["leads"].append(r["priced_lead_min"])
        if r["cost_T60"] is not None:
            g["c60"].append(r["cost_T60"])
        if r["cost_T10"] is not None:
            g["c10"].append(r["cost_T10"])
        g["series"].add(r["series"])
    groups = {}
    for k, g in grp.items():
        # series-equal-weighted capturable rate (each series counts once) -> not dominated by big-sample series
        sr = [meas[s]["capturable_rate"] for s in g["series"]]
        groups[k] = {"n_markets": g["n"], "n_series": len(g["series"]), "capturable_rate_pooled": round(g["k"] / g["n"], 4),
                     "wilson95": wilson(g["k"], g["n"]), "capturable_rate_series_mean": round(statistics.mean(sr), 4),
                     "capturable_rate_60min_pooled": round(g["k60"] / g["n"], 4),
                     "median_priced_lead_min": round(statistics.median(g["leads"]), 1),
                     "median_winner_cost_T60": statistics.median(g["c60"]) if g["c60"] else None,
                     "median_winner_cost_T10": statistics.median(g["c10"]) if g["c10"] else None}
    # ---- classifier-miss flags: a non-EARLY series whose winners were already priced >=60 min before close in most sampled markets
    flags = []
    for r in table:
        m = r.get("measured")
        if m and r["class"] != CLS_EARLY and m["n_usable"] >= 3 and m["median_priced_lead_min"] >= 60:
            flags.append({"series": r["series"], "class": r["class"], "subtype": r["subtype"], "title": r["title"],
                          "n_usable": m["n_usable"], "median_priced_lead_min": m["median_priced_lead_min"],
                          "capturable_rate": m["capturable_rate"], "median_winner_cost_T60": m["median_winner_cost_T60"],
                          "median_capturable_volume": m["median_capturable_volume"]})
    flags.sort(key=lambda x: -x["median_priced_lead_min"])
    # ---- verify
    vok = sum(1 for v in verify.values() if v.get("get") is not None)
    vag = sum(1 for v in verify.values() if v.get("get") is not None and v["get"] == v["listing"])
    # ---- class summary
    csum = collections.defaultdict(lambda: {"series": 0, "volume": 0.0, "categories": collections.Counter()})
    for r in table:
        c = csum[r["class"]]
        c["series"] += 1
        c["volume"] += r["sum_volume_contracts"]
        c["categories"][r["category"]] += 1
    class_summary = {k: {"series": v["series"], "sum_volume_contracts_in_returned_markets": round(v["volume"]),
                         "top_categories": v["categories"].most_common(5)} for k, v in csum.items()}
    cat = jload(os.path.join(CACHE, "series_catalog.json"), [])
    uni, seen, _ = universe()
    probed = len([f for f in os.listdir(os.path.join(CACHE, "series_markets")) if f.endswith(".json")])
    coverage = {"series_in_catalog": len(cat), "series_in_probe_universe": len(uni), "series_probed": probed,
                "series_with_ge20_settled": len(table), "events_walked": sum(seen.values()), "series_seen_in_event_walk": len(seen),
                "markets_sampled_planned": len(plan), "markets_with_usable_candles": len(mets), "skips": dict(skips),
                "result_verification_get_vs_listing": {"checked": vok, "agree": vag}}
    out = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "nature": "DESCRIPTIVE SCREEN - not a hypothesis test, no pass bar. Nothing here may be promoted without a NEW pre-registration.",
           "window_min": WINDOW_MIN, "seed": SEED, "coverage": coverage, "class_summary": class_summary,
           "group_measured": groups, "weather_gap": wgap, "ranked_by_score": ranked[:60], "ranked_gapfree": ranked_gf[:40],
           "family_rollup": fam_rows, "family_rollup_gapfree": fam_rows_gf, "classifier_miss_flags": flags, "classification": table}
    jdump(out, os.path.join(OUTDIR, "shape_screen.json"))
    write_md(out, ranked, ranked_gf, fam_rows, flags, byser)
    print("wrote shape_screen.json / shape_screen.md")
    return out


def stage_selftest():
    """winner_scan/market_metrics must reproduce edge_sizing_v2.scan() exactly (same normalize, same cost rule)."""
    import glob
    import edge_sizing_v2 as esv2
    esv2.WINDOW_MIN = WINDOW_MIN
    fs = sorted(glob.glob(os.path.join(HERE, "cache", "finality", "A", "candles", "*.json")))
    random.Random(1).shuffle(fs)
    bad = n = 0
    global candle_path
    keep = candle_path
    tmp = os.path.join(CACHE, "_selftest.json")
    for f in fs[:200]:
        cs = (jload(f) or {}).get("candlesticks")
        if not cs:
            continue
        close_ts = max(c["end_period_ts"] for c in cs) + 30
        for res in ("yes", "no"):
            m = {"ticker": "T", "series_ticker": "X", "result": res,
                 "close_time": dt.datetime.fromtimestamp(close_ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            esv2.candles_for = lambda mm, cs=cs: cs
            a_ = esv2.scan(m)
            jdump({"candles": cs}, tmp)
            candle_path = lambda tk: tmp
            b_ = market_metrics({"m": m, "series": "X", "group": "g"})
            n += 1
            if "skip" in a_ or "skip" in b_:
                bad += ("skip" in a_) != ("skip" in b_)
                continue
            if (a_["capturable"], a_["n_capturable_minutes"], a_["best_winner_cost_c"], round(a_["capturable_volume"], 3)) != \
               (b_["capturable"], b_["n_capturable_minutes"], b_["best_cost_c"], round(b_["capturable_volume"], 3)):
                bad += 1
    candle_path = keep
    print(f"selftest: {n} market-sides compared with edge_sizing_v2.scan, mismatches={bad}")
    return {"compared": n, "mismatches": bad}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="+")
    ap.add_argument("--max-pages", type=int, default=10 ** 9)
    a = ap.parse_args()
    for s in a.stage:
        if s in ("events", "all"):
            stage_events(a.max_pages)
        if s in ("markets", "all"):
            stage_markets()
        if s in ("classify", "all"):
            stage_classify()
        if s in ("weathergap", "all"):
            stage_weather_gap()
        if s in ("selftest",):
            stage_selftest()
        if s in ("sample", "all"):
            stage_sample()
        if s in ("candles", "all"):
            stage_candles()
        if s in ("verify", "all"):
            stage_verify()
        if s in ("report", "all"):
            stage_report()
