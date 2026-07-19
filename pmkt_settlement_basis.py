#!/usr/bin/env python3
"""pmkt_settlement_basis.py -- SETTLEMENT-BASIS study for the Polymarket daily temperature ladder.

WHY: wx_new_capacity_scan.md flagged Polymarket's 51-city daily high/low temperature bracket ladder as the
one genuinely new capacity candidate for K-WX, but explicitly left its settlement-source basis risk
UNMEASURED: Polymarket settles on a wunderground.com/history STATION-HISTORY PAGE SCRAPE, not the NWS CLI
report Kalshi settles on. K-WX's whole edge depends on a free, fast, real-time obs feed being a reliable
PREDICTOR of the eventual settlement value (Kalshi side: IEM/ASOS-vs-CLI is a measured 2.5% tail, see
kalshi_wx_settlement_basis.py). This script asks the same question for Polymarket: if a bot had watched the
free IEM daily-summary record (the same global ASOS/METAR network aviationweather.gov and the repo's
existing IEM fetch helpers already read) for the STATION Polymarket's rules name, would it have predicted
the settled bracket correctly, city by city?

METHOD (read-only, real API pulls, no trading code):
  1. For each sampled city, read the Gamma API market rules VERBATIM (event description + each rung's
     resolutionSource) to get the exact wunderground.com/history URL and station code the market cites.
  2. Identify the physical station behind that URL. For 9/10 sampled cities it's a METAR airport code
     (KORD, KBKF, KMIA, KLGA, EGLC, LFPB, MMMX, SBGR, RJTT) -- the SAME global ASOS/METAR network the repo's
     aviationweather.gov and IEM helpers already read. Hong Kong is the exception: its rules cite the HONG
     KONG OBSERVATORY (weather.gov.hk), NOT Wunderground and NOT the VHHH airport METAR -- a different
     station entirely (HKO's primary HQ site is ~30km from the airport), so it is excluded from the
     agreement measurement and flagged as its own quirk.
  3. Pull ~14 recent days of IEM's official daily max-temp summary (mesonet.agron.iastate.edu/cgi-bin/
     request/daily.py) for each station -- the same free real-time-obs-derived record a live bot would see
     (IEM's ASOS network mirror is global, confirmed to cover GB__ASOS/FR__ASOS/MX__ASOS/BR__ASOS/JP__ASOS/
     HK__ASOS, not just the US networks the repo's STATIONS dict lists today).
  4. Pull the RESOLVED Polymarket event for the same city-day (Gamma API, closed=true, outcomePrices
     ["1","0"] identifies the winning bracket rung) and parse its printed range.
  5. AGREEMENT = does the IEM daily max fall inside the winning bracket's printed range? This is the direct
     analog of the repo's ASOS-vs-CLI 1340/1340 check, at the scale this scan could pull politely (~130
     city-days). Also reports, per rung, HOW FAR the IEM value sits from a bracket edge (near-miss risk).

PROPOSE-ONLY: reads public data only (Polymarket Gamma API, IEM Mesonet). No auth, no orders, no strategy
code, no params touched. Caches all pulls under ./_pmkt_cache and ./_pmkt_basis_cache so reruns are cheap
and polite.
"""
import csv, io, json, os, ssl, sys, time, urllib.error, urllib.parse, urllib.request, datetime as dt

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; wx-pmkt-basis-study/1.0)"}

GBASE = "https://gamma-api.polymarket.com"
DAILY = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"

HERE = os.path.dirname(os.path.abspath(__file__))
PMKT_CACHE = os.path.join(HERE, "_pmkt_cache")
IEM_CACHE = os.path.join(HERE, "_pmkt_basis_cache")
os.makedirs(PMKT_CACHE, exist_ok=True)
os.makedirs(IEM_CACHE, exist_ok=True)

# --------------------------------------------------------------------------------------------------------
# Station catalog: for each sampled Polymarket city, the EXACT station+network the rules cite (verified
# against each event's `resolutionSource` / `description` field verbatim -- see the .md report for the raw
# text). unit = the market's bracket unit (F or C, per the "measures temperatures in whole degrees X"
# clause). step = bracket width in that unit (2 for the F cities sampled, 1 for the C cities sampled --
# read directly off the printed rung labels, not assumed).
# --------------------------------------------------------------------------------------------------------
STATIONS = {
    # city_slug: (station_id_for_iem, iem_network, wunderground_slug, unit, source_kind)
    "chicago":      ("ORD",  "IL_ASOS", "us/il/chicago/KORD",           "F", "wunderground"),
    "denver":       ("BKF",  "CO_ASOS", "us/co/aurora/KBKF",            "F", "wunderground"),
    "miami":        ("MIA",  "FL_ASOS", "us/fl/miami/KMIA",             "F", "wunderground"),
    "nyc":          ("LGA",  "NY_ASOS", "us/ny/new-york-city/KLGA",     "F", "wunderground"),
    "london":       ("EGLC", "GB__ASOS", "gb/london/EGLC",              "C", "wunderground"),
    "paris":        ("LFPB", "FR__ASOS", "fr/bonneuil-en-france/LFPB",  "C", "wunderground"),
    "mexico-city":  ("MMMX", "MX__ASOS", "mx/mexico-city/MMMX",         "C", "wunderground"),
    "sao-paulo":    ("SBGR", "BR__ASOS", "br/guarulhos/SBGR",           "C", "wunderground"),
    "tokyo":        ("RJTT", "JP__ASOS", "jp/tokyo/RJTT",               "C", "wunderground"),
    # Hong Kong deliberately NOT in the METAR agreement table: rules cite the Hong Kong Observatory
    # (weather.gov.hk "Absolute Daily Max", 0.1C precision), not Wunderground and not VHHH METAR. Kept
    # here (source_kind="hko") so the script still fetches VHHH for comparison and reports the DIVERGENCE
    # explicitly, rather than silently dropping the city.
    "hong-kong":    ("VHHH", "HK__ASOS", None,                          "C", "hko"),
}

# Low-temperature ladders: scan doc says only NYC and Miami list one.
LOW_CITIES = ["nyc", "miami"]

HKO_URL = "https://www.weather.gov.hk/en/cis/climat.htm"

N_DAYS = 14
END_DATE = dt.date(2026, 7, 18)   # last full day with a settled Polymarket outcome as of the 2026-07-19 run
START_DATE = END_DATE - dt.timedelta(days=N_DAYS - 1)


def _get(url, to=20, tries=3):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=to, context=_CTX))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"__404__": True}
            time.sleep(1.5 * (k + 1))
        except Exception as e:
            if k == tries - 1:
                return {"__err__": f"{type(e).__name__}: {e}"}
            time.sleep(1.5 * (k + 1))
    return {"__err__": "failed after retries"}


# --------------------------------------------------------------------------------------------------------
# Polymarket resolved events
# --------------------------------------------------------------------------------------------------------

def pmkt_slug(city_slug, kind, d):
    month = d.strftime("%B").lower()
    return f"{kind}-temperature-in-{city_slug}-on-{month}-{d.day}-{d.year}"


def fetch_event(slug):
    fp = os.path.join(PMKT_CACHE, f"{slug}.json")
    if os.path.exists(fp) and os.path.getsize(fp) > 20:
        return json.load(open(fp))
    d = _get(f"{GBASE}/events/slug/{slug}")
    with open(fp, "w") as f:
        json.dump(d, f)
    time.sleep(0.2)
    return d


def parse_bracket(label, unit):
    """'72-73°F' -> (72,73); '90°F or higher' -> (90, inf); '71°F or below' -> (-inf, 71);
    '30°C' (single-degree C rungs) -> (30, 30)."""
    s = label.replace("°F", "").replace("°C", "").strip()
    if "or below" in s or "or less" in s:
        hi = float(s.split()[0])
        return (float("-inf"), hi)
    if "or higher" in s or "or above" in s or "or more" in s:
        lo = float(s.split()[0])
        return (lo, float("inf"))
    if "-" in s:
        lo, hi = s.split("-")
        return (float(lo), float(hi))
    v = float(s)
    return (v, v)


def resolved_bracket(event):
    """Return (label, (lo,hi), unit_guess) for the winning rung of a CLOSED event, or None if not settled."""
    if not event or event.get("__404__") or "__err__" in event:
        return None
    mkts = event.get("markets", [])
    for m in mkts:
        if not m.get("closed"):
            return None
        try:
            prices = json.loads(m["outcomePrices"]) if isinstance(m["outcomePrices"], str) else m["outcomePrices"]
        except Exception:
            prices = m.get("outcomePrices") or []
        if prices and float(prices[0]) > 0.5:
            label = m.get("groupItemTitle", "")
            unit = "C" if "°C" in label else "F"
            return label, parse_bracket(label, unit), unit
    return None


# --------------------------------------------------------------------------------------------------------
# IEM daily summaries (free, real-time-obs-derived -- the analog of the repo's ASOS/METAR feed)
# --------------------------------------------------------------------------------------------------------

def fetch_iem_daily(stid, net, start, end):
    fp = os.path.join(IEM_CACHE, f"daily_{stid}_{start:%Y%m%d}_{end:%Y%m%d}.csv")
    if os.path.exists(fp) and os.path.getsize(fp) > 40:
        return open(fp, encoding="utf-8").read()
    q = urllib.parse.urlencode({"network": net, "stations": stid,
        "year1": start.year, "month1": start.month, "day1": start.day,
        "year2": end.year, "month2": end.month, "day2": end.day,
        "var": "max_temp_f,min_temp_f", "format": "comma"})
    req = urllib.request.Request(f"{DAILY}?{q}", headers={"User-Agent": "wx-pmkt-basis-study/1.0"})
    txt = urllib.request.urlopen(req, timeout=45, context=_CTX).read().decode("utf-8", "replace")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(txt)
    time.sleep(0.5)
    return txt


def parse_iem_daily(txt):
    """-> {date: {'max_f':..,'min_f':..}}"""
    out = {}
    rdr = csv.reader(io.StringIO(txt))
    header = None
    for row in rdr:
        if not row or row[0].startswith("#"):
            continue
        if header is None:
            header = row
            continue
        rec = dict(zip(header, row))
        try:
            d = dt.datetime.strptime(rec["day"], "%Y-%m-%d").date()
        except Exception:
            continue
        def fv(k):
            v = rec.get(k, "")
            return float(v) if v not in ("", "None", "M") else None
        out[d] = {"max_f": fv("max_temp_f"), "min_f": fv("min_temp_f")}
    return out


def f_to_c(f):
    return None if f is None else (f - 32.0) * 5.0 / 9.0


# --------------------------------------------------------------------------------------------------------
# Main measurement
# --------------------------------------------------------------------------------------------------------

def measure_city(city_slug, kind="highest"):
    stid, net, wu_slug, unit, source_kind = STATIONS[city_slug]
    iem_txt = fetch_iem_daily(stid, net, START_DATE - dt.timedelta(days=1), END_DATE)
    iem = parse_iem_daily(iem_txt)
    rows = []
    d = START_DATE
    while d <= END_DATE:
        slug = pmkt_slug(city_slug, kind, d)
        ev = fetch_event(slug)
        res = resolved_bracket(ev)
        rec = iem.get(d, {})
        obs_f = rec.get("max_f") if kind == "highest" else rec.get("min_f")
        if res is None or obs_f is None:
            rows.append({"date": d.isoformat(), "status": "unsettled_or_no_obs"})
            d += dt.timedelta(days=1)
            continue
        label, (lo, hi), bunit = res
        obs = obs_f if bunit == "F" else f_to_c(obs_f)
        # IEM's F->C round trip for whole-C-native METAR stations leaves sub-0.1 FP noise (e.g. 82.4F ->
        # 28.000000000000004C) that can flip an exact boundary reading to a false miss. The station's true
        # reporting precision is whole degrees (F or C per bunit), so round to 1 decimal before the bracket
        # check -- this removes the FP artifact without hiding any real sub-degree disagreement (a genuine
        # near-boundary case would show as e.g. .5, not .0000000000004).
        obs = round(obs, 1)
        agree = lo <= obs <= hi
        # distance to nearest bracket edge in bracket units (near-miss risk, negative if inside)
        if agree:
            edge_dist = min(obs - lo if lo != float("-inf") else float("inf"),
                             hi - obs if hi != float("inf") else float("inf"))
        else:
            edge_dist = -min(abs(obs - lo) if lo != float("-inf") else float("inf"),
                              abs(obs - hi) if hi != float("inf") else float("inf"))
        rows.append({"date": d.isoformat(), "status": "settled", "winning_rung": label,
                     "iem_obs": round(obs, 2), "bunit": bunit, "agree": agree,
                     "edge_dist": round(edge_dist, 2)})
        d += dt.timedelta(days=1)
    return {"city": city_slug, "kind": kind, "station": stid, "network": net, "source_kind": source_kind,
            "rows": rows}


def summarize(result):
    settled = [r for r in result["rows"] if r["status"] == "settled"]
    n = len(settled)
    agree = sum(1 for r in settled if r["agree"])
    near = [r["edge_dist"] for r in settled if r["agree"] and r["edge_dist"] < 1.0]
    return {"n_settled": n, "n_total": len(result["rows"]), "n_agree": agree,
            "agree_pct": (100.0 * agree / n) if n else None, "n_near_edge_lt1": len(near)}


CITY_MIX = ["chicago", "denver", "miami", "nyc", "london", "paris", "mexico-city", "sao-paulo", "tokyo",
            "hong-kong"]


def run():
    all_results = []
    print("=" * 100)
    print(f"PMKT SETTLEMENT-BASIS STUDY -- {N_DAYS} days ({START_DATE} to {END_DATE}), "
          f"{len(CITY_MIX)} cities (highest-temp ladder) + {len(LOW_CITIES)} lowest-temp ladders")
    print("=" * 100)
    for city in CITY_MIX:
        res = measure_city(city, "highest")
        all_results.append(res)
        s = summarize(res)
        tag = "HKO-DIVERGENCE (excluded from agreement claim)" if res["source_kind"] == "hko" else "wunderground/METAR"
        print(f"\n[{city:14}] station={res['station']:6} net={res['network']:10} src={tag}")
        print(f"  settled days: {s['n_settled']}/{s['n_total']}  |  IEM-vs-settled agreement: "
              f"{s['n_agree']}/{s['n_settled']} "
              f"({s['agree_pct']:.1f}%)" if s['n_settled'] else "  no settled days")
        for r in res["rows"]:
            if r["status"] != "settled":
                print(f"    {r['date']}  -- {r['status']}")
                continue
            flag = "OK" if r["agree"] else "MISS"
            near = " (near edge <1)" if r["agree"] and r["edge_dist"] < 1.0 else ""
            print(f"    {r['date']}  rung={r['winning_rung']:>14}  IEM_obs={r['iem_obs']:>6}{r['bunit']}  "
                  f"{flag}{near}")

    print("\n" + "-" * 100)
    print("LOW-TEMPERATURE LADDERS (NYC, Miami only per scan doc)")
    print("-" * 100)
    for city in LOW_CITIES:
        res = measure_city(city, "lowest")
        all_results.append(res)
        s = summarize(res)
        print(f"\n[{city:14} LOW] station={res['station']:6} net={res['network']}")
        print(f"  settled days: {s['n_settled']}/{s['n_total']}  |  IEM-vs-settled agreement: "
              f"{s['n_agree']}/{s['n_settled']} "
              f"({s['agree_pct']:.1f}%)" if s['n_settled'] else "  no settled days")
        for r in res["rows"]:
            if r["status"] != "settled":
                print(f"    {r['date']}  -- {r['status']}")
                continue
            flag = "OK" if r["agree"] else "MISS"
            near = " (near edge <1)" if r["agree"] and r["edge_dist"] < 1.0 else ""
            print(f"    {r['date']}  rung={r['winning_rung']:>14}  IEM_obs={r['iem_obs']:>6}{r['bunit']}  "
                  f"{flag}{near}")

    # aggregate, METAR-sourced cities only (excludes Hong Kong's HKO divergence by design)
    metar_results = [r for r in all_results if r["source_kind"] == "wunderground"]
    tot_settled = sum(len([x for x in r["rows"] if x["status"] == "settled"]) for r in metar_results)
    tot_agree = sum(sum(1 for x in r["rows"] if x["status"] == "settled" and x["agree"]) for r in metar_results)
    print("\n" + "=" * 100)
    print(f"POOLED (Wunderground/METAR-sourced cities+ladders, n={len(metar_results)} city-ladders): "
          f"{tot_agree}/{tot_settled} station-days agree "
          f"({100.0*tot_agree/tot_settled:.1f}%)" if tot_settled else "no settled days")
    print("Hong Kong excluded from the pooled number -- its rules cite the Hong Kong Observatory, not "
          "Wunderground/METAR (see report).")
    print("=" * 100)

    with open(os.path.join(HERE, "pmkt_settlement_basis_results.json"), "w") as f:
        json.dump(all_results, f, indent=1, default=str)
    print(f"\nwrote {os.path.join(HERE, 'pmkt_settlement_basis_results.json')}")


if __name__ == "__main__":
    run()
