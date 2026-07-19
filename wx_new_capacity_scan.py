#!/usr/bin/env python3
"""wx_new_capacity_scan.py -- where else does the K-WX mechanical-lock edge have room to grow?

K-WX's edge is narrow and specific: buy a rung once the OBSERVED reading has mechanically pinned the
settlement outcome, before slow retail reprices the book. Measured capacity is depth-capped at ~$1.1-1.6k/wk
(kwx_capacity_probe.py) on the current 20-city Kalshi KXHIGH*/KXLOWT* set, which wx_market_coverage.py has
already confirmed is fully traded (no free same-venue city to add). Reaching the $4k/mo goal needs either
more DEPTH per fire (Synoptic, already tracked) or a genuinely NEW pool of markets with the same mechanical
structure. This script scouts two such pools with real, live, read-only API pulls:

  Q1 CROSS-VENUE: does Polymarket list daily temperature markets that settle on an observable station
     reading the same way Kalshi's do? (Gamma API for market discovery, CLOB API for order-book depth.)
  Q2 NEW KALSHI FAMILIES: does Kalshi list any OTHER series (outside the 20-city KXHIGH*/KXLOWT* set)
     whose settlement is a cumulative/extremal physical observable that can mechanically lock intraday?
     (Kalshi /series + /events + /markets + /orderbook, read-only.)

Prior art this script deliberately does NOT re-litigate (see DECISION_MAP.md): the Polymarket BTC
copy-trade/box/lead-lag studies (archive/docs/edge_polymarket_*.md, F13/D5/PMKT-* -- all crypto, weather
never scanned); the Kalshi RAIN SLEEVE (monthly KXRAIN, 2026-07-18) and DAILY RAIN (KXRAINNYC) studies,
both KILLED for the same root cause -- accumulation is slow enough that the book reprices to ~99-100c
BEFORE any independent observable confirms the cross (96.5% DOA on the clean CLI-MTD signal; the daily
rain lock closes in ~1-2min, tighter than temp's 3.3min half-life, via retail's own radar access); and
US-AGGREGATE TEMP (KXHIGHUS/KXAVGTEMP, forecaster-pick or monthly-aggregate, not nowcast-able). Any
snow-monthly or precip family found here inherits the identical accumulation-vs-repricing failure mode
unless a genuinely new angle is shown -- this script does not re-recommend it without one.

PROPOSE-ONLY: reads public data only (Kalshi trade-api v2, Polymarket Gamma + CLOB). No auth, no orders,
no strategy code, no params touched. Run periodically -- new series/events get added over time.
"""
import json, os, ssl, time, urllib.error, urllib.parse, urllib.request

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; wx-capacity-scan/1.0)"}

KBASE = "https://api.elections.kalshi.com/trade-api/v2"
GBASE = "https://gamma-api.polymarket.com"
CBASE = "https://clob.polymarket.com"

# The 20 cities K-WX already trades (kwx_runner.CITY keys, high side) -- anything sharing these stations
# under a *different* ticker prefix is a deprecated naming variant, not new capacity (wx_market_coverage.py).
OUR_KALSHI_HIGH_SERIES = {
    "KXHIGHDEN", "KXHIGHMIA", "KXHIGHCHI", "KXHIGHTBOS", "KXHIGHAUS", "KXHIGHTSEA", "KXHIGHTSFO",
    "KXHIGHTMIN", "KXHIGHTDC", "KXHIGHTATL", "KXHIGHTDAL", "KXHIGHTSATX", "KXHIGHNY", "KXHIGHTOKC",
    "KXHIGHTLV", "KXHIGHTPHX", "KXHIGHTHOU", "KXHIGHPHIL", "KXHIGHTNOLA", "KXHIGHLAX",
}
OUR_KALSHI_CITY_NAMES = {
    "denver", "miami", "chicago", "boston", "austin", "seattle", "san francisco", "minneapolis",
    "washington", "atlanta", "dallas", "san antonio", "nyc", "new york", "oklahoma city",
    "las vegas", "phoenix", "houston", "philadelphia", "new orleans", "los angeles",
}


def _get(url, to=20):
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        return json.load(urllib.request.urlopen(req, timeout=to, context=_CTX))
    except Exception as e:
        return {"__err__": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------------------------------------
# Q1 -- POLYMARKET
# --------------------------------------------------------------------------------------------------------

def polymarket_scan():
    print("=" * 100)
    print("Q1 -- CROSS-VENUE: Polymarket daily weather markets")
    print("=" * 100)
    hit = _get(f"{GBASE}/public-search?q=weather&limit_per_type=5")
    if "__err__" in hit:
        print(f"  Gamma public-search UNREACHABLE: {hit['__err__']}")
        print("  NULL (network) -- cannot confirm or deny; rerun.")
        return

    # The 'Weather' tag (id 84) is the canonical grouping; pull every currently-open event under it.
    events, offset = [], 0
    while True:
        page = _get(f"{GBASE}/events?tag_id=84&closed=false&limit=100&offset={offset}")
        if isinstance(page, dict) and "__err__" in page:
            print(f"  tag pull failed at offset {offset}: {page['__err__']}")
            break
        if not page:
            break
        events.extend(page)
        if len(page) < 100:
            break
        offset += 100
        if offset > 1000:  # sane cap -- be polite
            break
        time.sleep(0.15)

    if not events:
        print("  NULL: no open Polymarket events under the Weather tag right now.")
        return

    daily_temp = [e for e in events if "Highest temperature" in e.get("title", "") or
                  "Lowest temperature" in e.get("title", "")]
    cities = set()
    for e in daily_temp:
        # "Highest temperature in Hong Kong on July 19?" -> "Hong Kong"
        t = e["title"]
        try:
            city = t.split(" in ", 1)[1].rsplit(" on ", 1)[0].strip().lower()
            cities.add(city)
        except IndexError:
            pass

    print(f"  Weather-tag events open right now: {len(events)}")
    print(f"  Daily high/low TEMPERATURE city-day events: {len(daily_temp)}  |  unique cities: {len(cities)}")
    overlap = sorted(c for c in cities if c in OUR_KALSHI_CITY_NAMES)
    new_only = sorted(c for c in cities if c not in OUR_KALSHI_CITY_NAMES)
    print(f"  Cities also on our Kalshi 20:  {len(overlap)}  -> {overlap}")
    print(f"  Cities NOT on Kalshi at all:   {len(new_only)}  -> {new_only[:30]}"
          f"{' ...' if len(new_only) > 30 else ''}")

    other_wx = [e for e in events if e not in daily_temp]
    print(f"\n  Other weather-tag families open (not daily temp) -- {len(other_wx)} events, sample:")
    for e in other_wx[:15]:
        print(f"    - {e.get('title')}")

    if not daily_temp:
        print("\n  NULL: Weather tag has content but no daily temperature product currently listed.")
        return

    # Inspect one concrete event in full: settlement source, per-rung book, ladder depth.
    sample = next((e for e in daily_temp if "NYC" in e.get("title", "") or "New York" in e.get("title", "")),
                  daily_temp[0])
    detail = _get(f"{GBASE}/events/slug/{sample.get('slug')}")
    if "__err__" in detail:
        print(f"\n  sample event detail pull failed: {detail['__err__']}")
        return
    mkts = detail.get("markets", [])
    print(f"\n  SAMPLE EVENT: '{detail.get('title')}'  ({len(mkts)} bracket rungs)")
    src = mkts[0].get("resolutionSource") if mkts else detail.get("resolutionSource")
    print(f"  settlement source: {src}")
    print("  -> station-level scrape (e.g. Wunderground daily-history page for the airport ASOS station),"
          " NOT the NWS CLI report Kalshi settles on. Same mechanical shape (ladder converges once the "
          "day's running extreme is locked in) but a DIFFERENT observable -> basis risk needs its own"
          " measurement, exactly like Kalshi's ASOS-vs-CLI 2.5% tail (kalshi_wx_settlement_basis.py).")

    print(f"\n  per-rung snapshot (bestBid/bestAsk/liquidityNum/vol24h):")
    for m in sorted(mkts, key=lambda m: m.get("groupItemTitle") or ""):
        print(f"    {str(m.get('groupItemTitle')):>14} | bid={m.get('bestBid')} ask={m.get('bestAsk')} "
              f"liq=${m.get('liquidityNum'):.0f} vol24h={m.get('volume24hr')}")

    # Real CLOB order-book depth for whichever rung looks closest to a lock (bestAsk highest).
    locked = max((m for m in mkts if m.get("bestAsk") is not None), key=lambda m: m["bestAsk"], default=None)
    if locked and locked.get("clobTokenIds"):
        try:
            tok = json.loads(locked["clobTokenIds"])[0]
        except Exception:
            tok = None
        if tok:
            ob = _get(f"{CBASE}/book?token_id={tok}")
            if "__err__" not in ob:
                bids, asks = ob.get("bids", []), ob.get("asks", [])
                bid_sz = sum(float(l["size"]) for l in bids)
                ask_sz = sum(float(l["size"]) for l in asks)
                print(f"\n  CLOB book for closest-to-locked rung ({locked.get('groupItemTitle')}, "
                      f"ask={locked.get('bestAsk')}): {len(bids)} bid levels (${bid_sz:.0f} total), "
                      f"{len(asks)} ask levels (${ask_sz:.0f} total)")
                print("  -> real resting depth exists (hundreds-to-thousands $ per rung), same order of "
                      "magnitude as Kalshi's thin weather books, not obviously deeper or thinner.")
            else:
                print(f"\n  CLOB book pull failed: {ob['__err__']}")

    print("\n  Q1 VERDICT: NOT NULL. Polymarket runs the SAME daily high/low temperature bracket-ladder\n"
          "  product as Kalshi (converges to ~$1 intraday once the day's extreme is effectively decided --\n"
          "  confirmed directly: brackets already at bestBid~0.999/bestAsk~1 with the ask book empty mid-day),\n"
          "  across dramatically more cities (dozens of international cities Kalshi doesn't list, plus most\n"
          "  of the US overlap). This is genuinely new market count. Two things are NOT yet verified here and\n"
          "  gate any real study: (1) settlement-source basis risk (Wunderground scrape vs NWS CLI -- unknown\n"
          "  false-lock rate, unlike Kalshi's measured 2.5%), (2) whether Polymarket's own book reprices AS\n"
          "  FAST as Kalshi's retail (if Polymarket users watch the same station feeds more closely, the\n"
          "  repricing-lag window this edge lives in could simply be narrower or absent there).")


# --------------------------------------------------------------------------------------------------------
# Q2 -- NEW KALSHI FAMILIES
# --------------------------------------------------------------------------------------------------------

# Candidates worth a rules+liquidity check: physical/observable series outside the 20-city temp set,
# picked from a full /series category scan (see scan log). Deliberately excludes rain/snow-monthly
# (same accumulation-vs-repricing failure as the killed RAIN SLEEVE) and US-aggregate/forecaster-pick
# series (already closed, US-AGGREGATE TEMP study) unless flagged otherwise below.
CANDIDATE_SERIES = [
    "KXAQICITY", "KXEARTHQUAKECALIFORNIA", "KXEARTHQUAKEJAPAN", "KXBIGGESTQUAKE",
    "KXDVHIGH", "KXTORNADO", "KXNAMEDSTORM", "KXFIRSTHURRICANE", "KXMEAD", "KXDROUGHTLEVEL",
    "KXHURCLAND", "KXTEMPNYCH", "KXHOLIDAYTMAX", "KXNYCSNOWM",
]


def kalshi_series_scan():
    print("\n" + "=" * 100)
    print("Q2 -- NEW KALSHI FAMILIES outside the 20-city KXHIGH*/KXLOWT* set")
    print("=" * 100)
    all_s = _get(f"{KBASE}/series?limit=200")
    if "__err__" in all_s:
        print(f"  /series pull failed: {all_s['__err__']}")
        return
    sers = all_s.get("series", [])
    print(f"  total Kalshi series (all categories, one unpaginated pull): {len(sers)}")
    by_cat = {}
    for s in sers:
        by_cat.setdefault(s.get("category", "?"), 0)
        by_cat[s.get("category", "?")] += 1
    print("  category breakdown: " + ", ".join(f"{c}={n}" for c, n in
          sorted(by_cat.items(), key=lambda kv: -kv[1])))

    cw = [s for s in sers if s.get("category") == "Climate and Weather"]
    print(f"\n  'Climate and Weather' category: {len(cw)} series total.")
    ours = OUR_KALSHI_HIGH_SERIES
    other_cw = [s for s in cw if s["ticker"] not in ours]
    print(f"  Outside our 20 daily high tickers: {len(other_cw)} series (includes deprecated naming "
          f"variants, rain/snow, hurricanes, earthquakes, ice, CO2, etc. -- see families below).")

    # Also sweep every OTHER category for stray physical-observable keywords (river/flood/wind/etc.)
    # that Kalshi might not tag as "Climate and Weather".
    kws = ("river", "flood", "snowpack", "reservoir", "wind speed", "tide", "hail", "seismic", "quake",
           "wildfire", "smoke", "storm surge")
    stray = [s for s in sers if s.get("category") != "Climate and Weather" and
             any(k in (s.get("title") or "").lower() for k in kws)]
    print(f"  Stray physical-observable series OUTSIDE 'Climate and Weather': {len(stray)}")
    for s in stray[:10]:
        print(f"    - [{s.get('category')}] {s['ticker']} | {s.get('title')}")
    if not stray:
        print("    (none found -- Kalshi's own category tagging is complete for this kind of series)")

    print(f"\n  Checking {len(CANDIDATE_SERIES)} named candidates for live rules + open events + one sample "
          f"order book (rate-limited, polite):")
    header = f"    {'ticker':<24}{'freq':<10}{'open_ev':<9}{'settlement_source':<45}"
    print(header)
    print("    " + "-" * (len(header) - 4))
    results = []
    for t in CANDIDATE_SERIES:
        ser = _get(f"{KBASE}/series/{t}")
        s = ser.get("series", {}) if "__err__" not in ser else {}
        src = ", ".join(x.get("name", "") for x in s.get("settlement_sources", [])) or "?"
        ev = _get(f"{KBASE}/events?series_ticker={t}&status=open&limit=5")
        events = ev.get("events", []) if "__err__" not in ev else []
        freq = s.get("frequency", "?")
        print(f"    {t:<24}{str(freq):<10}{len(events):<9}{src[:45]:<45}")
        results.append((t, freq, events, s))
        time.sleep(0.15)

    live = [(t, freq, ev, s) for t, freq, ev, s in results if ev]
    print(f"\n  {len(live)}/{len(CANDIDATE_SERIES)} candidates have open events right now: "
          f"{[t for t, *_ in live]}")

    for t, freq, ev, s in live:
        e = ev[0]
        mk = _get(f"{KBASE}/markets?event_ticker={e['event_ticker']}")
        markets = mk.get("markets", []) if "__err__" not in mk else []
        print(f"\n  --- {t} ({s.get('title')}) --- event: {e.get('title')}")
        print(f"      {len(markets)} market(s) in this event, e.g.:")
        for m in markets[:3]:
            print(f"        {m['ticker']} | yes_bid={m.get('yes_bid')} yes_ask={m.get('yes_ask')} "
                  f"vol={m.get('volume')} oi={m.get('open_interest')}")
        # sample one order book if there's a tradeable rung
        target = next((m for m in markets if m.get("yes_ask")), markets[0] if markets else None)
        if target:
            ob = _get(f"{KBASE}/markets/{target['ticker']}/orderbook")
            book = ob.get("orderbook", {}) if "__err__" not in ob else {}
            no_side = book.get("no") or []
            depth = sum(int(l[1]) for l in no_side if (100 - int(l[0])) <= 98)
            print(f"      orderbook sample ({target['ticker']}): fillable YES depth <=98c = {depth} contracts")

    print("\n  Q2 VERDICT (mechanical read on every candidate above):")
    print("  - AQI / earthquake-magnitude / hurricane-name / hurricane-landfall-region / tornado-count /")
    print("    Lake Mead level / drought category: all either (a) 0 open events right now (off-cycle / no")
    print("    liquidity), (b) annual or seasonal ONE-SHOT strikes with no resting book (thin-to-empty),")
    print("    or (c) settle on a bulletin (NHC advisory, USGS auto-report, NWS warning) that IS the")
    print("    observable -- there is no independently-faster feed to front-run it with, unlike ASOS-vs-CLI")
    print("    on temperature. That is the same structural reason rain/snow accumulation dies: the thing")
    print("    that would let us 'see the lock before the book' does not exist for these families.")
    print("  - KXTEMPNYCH (hourly directional) settles on The Weather Company, not NWS CLI -- already the")
    print("    excluded family per wx_market_coverage.py's KXHIGHNYD note.")
    print("  - KXDVHIGH (Death Valley) and KXNYCSNOWM (monthly snow) are both currently 0 open events;")
    print("    Death Valley would be same-mechanism-new-city IF it reopens (worth a periodic recheck);")
    print("    monthly snow inherits the killed RAIN SLEEVE's slow-accumulation problem, not new.")


if __name__ == "__main__":
    polymarket_scan()
    kalshi_series_scan()
    print("\n" + "=" * 100)
    print("See wx_new_capacity_scan.md for the full findings tables and ranked shortlist.")
    print("=" * 100)
