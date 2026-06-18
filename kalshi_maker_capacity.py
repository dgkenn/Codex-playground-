#!/usr/bin/env python3
"""
kalshi_maker_capacity.py
========================
CAPACITY & FILL REALISM for a small retail MAKER on Kalshi SOFT (non-crypto) markets.

Question: even if a favorite-longshot maker edge exists, can a $100-$1000 account
actually get *filled passively*, and how much $/month can it extract before its own
size moves the price?

Uses ONLY the public Kalshi API (no auth):
  base = https://api.elections.kalshi.com/trade-api/v2
  GET /series?category=<cat>
  GET /markets?series_ticker=<tk>&status=settled
  GET /series/<s>/markets/<mkt>/candlesticks?start_ts&end_ts&period_interval=60
  GET /markets/trades?ticker=<mkt>&limit=1000

We MEASURE, per market and aggregated by category:
  (1) total volume (contracts & $) over the market's life
  (2) volume time-distribution (front / steady / settlement-loaded) via candlesticks
  (3) typical touch size + how often the touch trades (from trades stream)
  (4) realistic passive FILL RATE: of the taker volume, how much would lift a resting
      maker quote at the touch. We split taker-buys (lift ask) vs taker-sells (hit bid).
      A passive maker on ONE side captures ~ the taker flow that crosses to that side,
      throttled by (a) queue position and (b) the fraction of life the maker is at touch.
  (5) translate to $/day and $/month a $100-$1000 maker could realistically capture,
      BEFORE the position moves the price (capacity = min(flow-limited, bankroll-limited)).

Honest accounting of haircuts is in the constants below.
"""
import urllib.request, urllib.parse, json, datetime, time, sys, math
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CATEGORIES = ["Economics", "Politics", "Climate and Weather",
              "Entertainment", "Science and Technology"]
MIN_VOL = 300.0          # require volume_fp >= 300 contracts
MAX_SERIES_PER_CAT = 40  # cap API load per category
MAX_MARKETS_PER_SERIES = 60
TRADE_PAGES = 3          # up to 3000 trades/market

# ---- Maker realism haircuts (documented assumptions) ----
# Of the taker flow that crosses to ONE side of the book, what fraction actually
# lifts OUR resting clip rather than someone else already at the touch.
QUEUE_CAPTURE = 0.25     # we win the queue ~25% of the time at a quiet touch
TOUCH_PRESENCE = 0.60    # we're posted at the touch ~60% of the market's active life
# Edge captured per filled contract (favorite-longshot maker spread, net of fees),
# in DOLLARS per contract. Spread on these markets is ~1-3c; net maker edge ~1c.
EDGE_PER_CONTRACT = 0.01
CLIP_LO, CLIP_HI = 100.0, 1000.0   # bankroll clip range ($)

UA = {"User-Agent": "kalshi-maker-capacity/1.0"}

def get(path, params=None, retries=4):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5 * (2 ** i))
    raise last

def ts(s):
    return int(datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())

def f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d

# ---------------------------------------------------------------------------
def list_series(cat):
    d = get("/series", {"category": cat})
    return [s["ticker"] for s in d.get("series", [])]

def settled_markets(series_tk):
    out, cursor = [], None
    while True:
        params = {"series_ticker": series_tk, "status": "settled", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = get("/markets", params)
        out.extend(d.get("markets", []))
        cursor = d.get("cursor")
        if not cursor or len(out) >= MAX_MARKETS_PER_SERIES:
            break
    return out

def is_tradeable_soft(m):
    if m.get("mve_collection_ticker"):
        return False
    if m.get("market_type") != "binary":
        return False
    if f(m.get("volume_fp")) < MIN_VOL:
        return False
    return True

def candle_distribution(series_tk, ticker, open_time, close_time):
    """Return (life_hours, frac_first_third, frac_mid_third, frac_last_third,
              active_hours_frac) of volume across the market's life."""
    try:
        st, en = ts(open_time), ts(close_time)
    except Exception:
        return None
    if en <= st:
        return None
    try:
        c = get(f"/series/{series_tk}/markets/{ticker}/candlesticks",
                {"start_ts": st, "end_ts": en, "period_interval": 60})
    except Exception:
        return None
    cs = c.get("candlesticks", [])
    if not cs:
        return None
    vols = []
    for k in cs:
        ept = k.get("end_period_ts")
        v = f(k.get("volume_fp"))
        if ept is not None:
            vols.append((ept, v))
    if not vols:
        return None
    total = sum(v for _, v in vols)
    if total <= 0:
        return None
    span = en - st
    b = [0.0, 0.0, 0.0]
    active = 0
    for ept, v in vols:
        frac = (ept - st) / span
        idx = 0 if frac < 1/3 else (1 if frac < 2/3 else 2)
        b[idx] += v
        if v > 0:
            active += 1
    life_h = span / 3600.0
    return dict(life_h=life_h,
                first=b[0]/total, mid=b[1]/total, last=b[2]/total,
                active_frac=active / max(1, len(vols)))

def trade_stats(ticker):
    """Pull trades, compute taker-buy vs taker-sell volume, $ volume, touch size,
    and how often the touch trades."""
    buys = sells = 0.0          # contracts by taker direction
    dollar_vol = 0.0
    sizes = []
    cursor = None
    n = 0
    for _ in range(TRADE_PAGES):
        params = {"ticker": ticker, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        try:
            d = get("/markets/trades", params)
        except Exception:
            break
        trs = d.get("trades", [])
        for t in trs:
            cnt = f(t.get("count_fp"))
            yp = f(t.get("yes_price_dollars"))
            side = t.get("taker_side")
            sizes.append(cnt)
            dollar_vol += cnt * yp        # notional at yes price
            if side == "yes":             # taker buys YES -> lifts the YES ask
                buys += cnt
            elif side == "no":            # taker buys NO -> hits the YES bid
                sells += cnt
        n += len(trs)
        cursor = d.get("cursor")
        if not cursor or not trs:
            break
    if not sizes:
        return None
    sizes.sort()
    median_size = sizes[len(sizes)//2]
    return dict(trades=n, buys=buys, sells=sells, dollar_vol=dollar_vol,
                median_clip=median_size, ntrades=len(sizes))

# ---------------------------------------------------------------------------
def main():
    quick = "--quick" in sys.argv
    if quick:
        global MAX_SERIES_PER_CAT
        MAX_SERIES_PER_CAT = 6

    cat_agg = {}
    per_market_rows = []

    for cat in CATEGORIES:
        print(f"\n=== {cat} ===", file=sys.stderr)
        try:
            series = list_series(cat)
        except Exception as e:
            print("  series err", e, file=sys.stderr)
            continue

        agg = dict(markets=0, vol=0.0, dollar=0.0,
                   first=0.0, mid=0.0, last=0.0, active=0.0,
                   buys=0.0, sells=0.0, life_h=0.0, ndist=0, clips=[])
        scanned = 0
        for stk in series:
            if scanned >= MAX_SERIES_PER_CAT:
                break
            try:
                mkts = settled_markets(stk)
            except Exception:
                continue
            tradeable = [m for m in mkts if is_tradeable_soft(m)]
            if not tradeable:
                continue
            scanned += 1
            # sample up to a few high-volume markets per series for trades/candles
            tradeable.sort(key=lambda m: -f(m.get("volume_fp")))
            sample = tradeable[:3 if not quick else 1]
            for m in tradeable:
                agg["markets"] += 1
                agg["vol"] += f(m.get("volume_fp"))
            for m in sample:
                tk = m["ticker"]
                dist = candle_distribution(stk, tk, m.get("open_time"), m.get("close_time"))
                tst = trade_stats(tk)
                if dist:
                    agg["first"] += dist["first"]; agg["mid"] += dist["mid"]
                    agg["last"] += dist["last"]; agg["active"] += dist["active_frac"]
                    agg["life_h"] += dist["life_h"]; agg["ndist"] += 1
                if tst:
                    agg["dollar"] += tst["dollar_vol"]
                    agg["buys"] += tst["buys"]; agg["sells"] += tst["sells"]
                    agg["clips"].append(tst["median_clip"])
                per_market_rows.append(dict(cat=cat, series=stk, ticker=tk,
                    vol=f(m.get("volume_fp")), dist=dist, tst=tst))
        cat_agg[cat] = agg
        print(f"  tradeable markets: {agg['markets']}, sampled dist {agg['ndist']}",
              file=sys.stderr)

    report(cat_agg, per_market_rows)

def report(cat_agg, rows):
    lines = []
    P = lines.append
    P("# RAW MEASUREMENTS (machine output)\n")
    grand = dict(markets=0, vol=0.0, daily=0.0)
    for cat, a in cat_agg.items():
        nd = max(1, a["ndist"])
        avg_life_h = a["life_h"] / nd
        first = a["first"]/nd; mid = a["mid"]/nd; last = a["last"]/nd
        active = a["active"]/nd
        clips = sorted(a["clips"])
        med_clip = clips[len(clips)//2] if clips else 0
        # Sampled taker flow split
        flow = a["buys"] + a["sells"]
        # Per-market AVERAGE life volume (contracts), using all tradeable markets:
        avg_vol = a["vol"] / max(1, a["markets"])
        # ---- Fill-rate model ----
        # A one-sided passive maker captures the taker flow crossing to its side.
        # On a favorite-longshot maker we mostly sell the favorite / buy the longshot,
        # so assume we engage ~half the two-sided flow. Capture = that flow *
        # QUEUE_CAPTURE * TOUCH_PRESENCE.
        capturable_per_mkt = 0.5 * avg_vol * QUEUE_CAPTURE * TOUCH_PRESENCE
        # spread that capacity over the market's life (days)
        life_days = max(avg_life_h/24.0, 0.5)
        # Per simultaneously-tradeable market $/day at touch:
        contracts_per_day = capturable_per_mkt / life_days
        usd_per_day_per_mkt = contracts_per_day * EDGE_PER_CONTRACT
        # How many such markets can one small account realistically watch+quote? ~5.
        concurrent = 5
        usd_day_cat = usd_per_day_per_mkt * concurrent
        P(f"## {cat}")
        P(f"- tradeable settled markets (vol>=300): **{a['markets']}**")
        P(f"- avg life volume/market: **{avg_vol:,.0f} contracts**")
        P(f"- avg market life: **{avg_life_h/24:.1f} days**, active hours frac: **{active:.0%}**")
        P(f"- volume time-distribution (first/mid/last third of life): "
          f"**{first:.0%} / {mid:.0%} / {last:.0%}**")
        P(f"- median trade clip (touch size): **{med_clip:.0f} contracts**")
        P(f"- sampled taker flow split buys/sells: {a['buys']:,.0f} / {a['sells']:,.0f}")
        P(f"- est capturable contracts/market-life: **{capturable_per_mkt:,.0f}** "
          f"(0.5 x vol x queue {QUEUE_CAPTURE} x presence {TOUCH_PRESENCE})")
        P(f"- => **${usd_per_day_per_mkt:.2f}/day per market**, "
          f"**${usd_day_cat:.2f}/day** running {concurrent} markets, "
          f"**${usd_day_cat*30:.0f}/month**\n")
        grand["markets"] += a["markets"]
        grand["vol"] += a["vol"]
        grand["daily"] += usd_day_cat
    P("## GRAND TOTAL")
    P(f"- total tradeable markets scanned: {grand['markets']}")
    P(f"- blended capacity ceiling: **${grand['daily']:.2f}/day "
      f"~ ${grand['daily']*30:.0f}/month** (one account, ~5 mkts/category overlap not additive)")
    out = "\n".join(lines)
    print(out)
    with open("CAPACITY_RAW.txt", "w") as fh:
        fh.write(out)

if __name__ == "__main__":
    main()
