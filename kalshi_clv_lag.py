#!/usr/bin/env python3
"""
kalshi_clv_lag.py -- the EMPIRICAL backtest substrate for the Kalshi-vs-sharp edge.

Builds on kalshi_vs_sharp.py (live deviation snapshot) by adding the two things the
prior SPORTS_BETTING.md said it lacked:

  (A) A SELF-CONTAINED Kalshi CLV / calibration backtest that needs NO external feed.
      Kalshi settled game markets expose 1-minute bid/ask OHLC CANDLESTICKS plus the
      realized result (yes/no). So we can measure, on Kalshi alone:
        - Brier(entry mid) vs Brier(closing/last mid)  -> does the price get sharper
          toward settlement? (the closing-line-is-sharpest law, on Kalshi's own book)
        - calibration buckets (is Kalshi's price biased anywhere -> exploitable?)
        - "entry-to-close drift" = the CLV a hypothetical entry would have captured.
      This is the honest in-sample test of "is Kalshi efficient" that does not need a key.

  (B) The TIMING-LAG harness design + glue. The full lag test (does Kalshi follow a
      sharp move with a capturable lag?) needs a TIME-STAMPED sharp feed. With an
      ODDS_API_KEY (the-odds-api, includes Pinnacle EU h2h) you poll Pinnacle every
      ~5 min and align to the Kalshi 1-min candlesticks; cross-correlate d(Pinnacle)
      with d(Kalshi) at lags 0..N min. Without a key, this prints the exact procedure
      and the data volume needed, and runs (A) so there is a measured result today.

Endpoints used (public, no auth):
  GET /trade-api/v2/events?series_ticker=KXMLBGAME&status=settled&with_nested_markets=true
  GET /trade-api/v2/series/{series}/markets/{ticker}/candlesticks?start_ts&end_ts&period_interval=60

Kalshi cost model:
  taker fee  = ceil(0.07*P*(1-P)*100)/100   per contract (paid once, hold-to-settle)
  maker fee  = 0  (and Liquidity Incentive pays up to +$0.005/contract) -> the lag edge,
               if real, is harvested as a MAKER resting ahead of the lagging follow.
"""
import os, sys, time, math, json, datetime, statistics
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ODDS_KEY = os.environ.get("ODDS_API_KEY")
S = requests.Session(); S.headers.update({"Accept": "application/json"})

LEAGUES = ["KXMLBGAME", "KXNHLGAME", "KXWNBAGAME", "KXNFLGAME", "KXNBA"]
ODDS_SPORT = {"KXMLBGAME": "baseball_mlb", "KXNBA": "basketball_nba",
              "KXNHLGAME": "icehockey_nhl", "KXNFLGAME": "americanfootball_nfl",
              "KXWNBAGAME": "basketball_wnba"}


def fl(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def taker_fee(p):
    if p is None: return None
    return math.ceil(0.07 * p * (1 - p) * 100) / 100


def kget(path, **p):
    for a in range(4):
        try:
            r = S.get(BASE + path, params=p, timeout=25)
            if r.status_code == 200: return r.json()
            if r.status_code == 429: time.sleep(2 ** a); continue
            return {"_err": r.status_code}
        except Exception: time.sleep(2 ** a)
    return {"_err": "fail"}


def settled_events(series, n=120):
    out, cursor = [], None
    while len(out) < n:
        p = {"series_ticker": series, "status": "settled",
             "limit": 50, "with_nested_markets": "true"}
        if cursor: p["cursor"] = cursor
        d = kget("/events", **p)
        evs = d.get("events", [])
        if not evs: break
        out += evs
        cursor = d.get("cursor")
        if not cursor: break
    return out[:n]


def market_candles(ticker, close_iso, hours_back=8):
    """1-min bid/ask OHLC candles for the hours before close. Returns list of
    (ts, mid, bid, ask, vol). Only candles with a real two-sided quote are kept."""
    series = ticker.split("-")[0]
    try:
        cdt = datetime.datetime.fromisoformat(close_iso.replace("Z", "+00:00"))
    except Exception:
        return []
    end = int(cdt.timestamp()); start = end - hours_back * 3600
    r = kget(f"/series/{series}/markets/{ticker}/candlesticks",
             start_ts=start, end_ts=end, period_interval=60)
    rows = []
    for x in r.get("candlesticks", []):
        yb = fl((x.get("yes_bid") or {}).get("close_dollars"))
        ya = fl((x.get("yes_ask") or {}).get("close_dollars"))
        if yb and ya and 0 < yb < ya < 1:
            rows.append((x["end_period_ts"], (yb + ya) / 2, yb, ya, fl(x.get("volume_fp")) or 0))
    return rows


# ----------------------------- (A) Kalshi-only CLV / calibration -----------------------------
def kalshi_self_backtest(max_games=120):
    print("=== (A) KALSHI-ONLY CLV / CALIBRATION BACKTEST (no external feed) ===")
    rows = []  # (entry_mid, last_mid, y, league, ticker)
    for lg in LEAGUES:
        evs = settled_events(lg, max_games)
        for ev in evs:
            for m in ev.get("markets", []):
                res = m.get("result")
                if res not in ("yes", "no"):
                    continue
                ct = m.get("close_time")
                if not ct:
                    continue
                c = market_candles(m["ticker"], ct, hours_back=8)
                if not c:
                    continue
                entry_mid = c[0][1]; last_mid = c[-1][1]
                y = 1 if res == "yes" else 0
                rows.append((entry_mid, last_mid, y, lg, m["ticker"]))
        if rows:
            print(f"  {lg}: cumulative usable games={len(rows)}")
    if not rows:
        print("  no settled candlestick data returned (off-season / quiet window).")
        return rows
    n = len(rows)
    bri_e = sum((p - y) ** 2 for p, _, y, *_ in rows) / n
    bri_l = sum((p - y) ** 2 for _, p, y, *_ in rows) / n
    # log-loss (clipped)
    def ll(idx):
        s = 0.0
        for r in rows:
            p = min(max(r[idx], 1e-4), 1 - 1e-4); y = r[2]
            s += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        return s / n
    print(f"\n  games={n}")
    print(f"  Brier(entry mid) = {bri_e:.4f}   logloss(entry) = {ll(0):.4f}")
    print(f"  Brier(close mid) = {bri_l:.4f}   logloss(close) = {ll(1):.4f}")
    print(f"  -> closing price {'IS sharper' if bri_l < bri_e else 'NOT sharper'} "
          f"(law: the closing line is the gold-standard sharpest predictor).")
    # calibration on the CLOSING mid (the sharp Kalshi estimate)
    print("\n  calibration of CLOSING mid (predicted vs realized):")
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        hi = lo + 0.2
        b = [(p, y) for _, p, y, *_ in rows if lo <= p < hi]
        if b:
            pred = sum(p for p, _ in b) / len(b); act = sum(y for _, y in b) / len(b)
            print(f"    [{lo:.1f}-{hi:.1f}) n={len(b):3d} pred={pred:.3f} actual={act:.3f} "
                  f"gap={ (act-pred)*100:+.1f}c")
    # CLV a naive 'enter at first quote' would have captured (drift toward winner)
    clv = [ (lm - em) if y == 1 else (em - lm) for em, lm, y, *_ in rows ]
    print(f"\n  mean entry->close drift toward realized winner = {statistics.mean(clv)*100:+.2f}c")
    print("    (positive = early Kalshi quotes are slightly soft vs close; but this is the price")
    print("     getting sharper as info arrives, NOT necessarily a takeable retail edge.)")
    return rows


# ----------------------------- (B) timing-lag harness (needs sharp feed) -----------------------------
def pinnacle_h2h(sport_key):
    if not ODDS_KEY:
        return None
    r = S.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
              params={"apiKey": ODDS_KEY, "regions": "eu", "markets": "h2h",
                      "oddsFormat": "decimal"}, timeout=20)
    if r.status_code != 200:
        print(f"  odds-api {sport_key}: {r.status_code} {r.text[:120]}"); return None
    out = []
    for g in r.json():
        pin = next((b for b in g.get("bookmakers", []) if b["key"] == "pinnacle"), None)
        if not pin:
            continue
        h2h = next((m for m in pin["markets"] if m["key"] == "h2h"), None)
        if not h2h or len(h2h["outcomes"]) != 2:
            continue
        o = h2h["outcomes"]; inv = [1 / x["price"] for x in o]; tot = sum(inv)
        out.append({"home": g.get("home_team"), "away": g.get("away_team"),
                    "ts": time.time(),
                    "probs": {o[i]["name"]: inv[i] / tot for i in range(2)},
                    "hold": tot - 1})
    return out


def lag_harness_note():
    print("\n=== (B) TIMING-LAG HARNESS (needs time-stamped sharp feed) ===")
    if not ODDS_KEY:
        print("  [no ODDS_API_KEY] -> design only. To run the real lag test:")
        print("   1. Pick in-season liquid games (MLB/NHL primetime, NFL/NBA in season).")
        print("   2. Every ~5 min from line-open to close, poll Pinnacle h2h (the-odds-api,")
        print("      'eu' region returns Pinnacle), de-vig to a fair prob, timestamp it.")
        print("   3. After settlement, pull Kalshi 1-min candlesticks for the same game.")
        print("   4. Align series; compute d(Pinnacle_fair) and d(Kalshi_mid) per minute;")
        print("      cross-correlate at lags 0..15 min. A positive peak at lag>0 means")
        print("      Kalshi FOLLOWS Pinnacle -> a MAKER resting at the post-move fair value")
        print("      (0 fee, +$0.005 LIP rebate) captures the lag. A peak at lag<=0 (or flat)")
        print("      means Kalshi leads/coincident -> NO capturable lag (SIG keeps it on consensus).")
        print("   5. Proof = positive realized CLV vs Kalshi settlement net of cost, OOS,")
        print("      over >=300-500 games / several weeks (same bar as the weather/PM studies).")
        print("   DATA NEEDED: ~1 ODDS_API_KEY (free 500 req/mo polls a few leagues a few x/day;")
        print("   Business tier $99/mo for dense polling) + ~3-6 weeks of in-season collection.")
        return
    print("  ODDS_API_KEY present -> point-in-time deviation snapshot vs Pinnacle:")
    devs = []
    for lg in LEAGUES:
        sk = ODDS_SPORT.get(lg)
        if not sk:
            continue
        pin = pinnacle_h2h(sk)
        if not pin:
            continue
        evs = kget("/events", series_ticker=lg, status="open",
                   limit=60, with_nested_markets="true").get("events", [])
        for ev in evs:
            mk = [m for m in ev.get("markets", []) if fl(m.get("yes_bid_dollars")) and fl(m.get("yes_ask_dollars"))]
            if len(mk) != 2:
                continue
            for m in mk:
                title = (m.get("yes_sub_title") or m.get("title") or "").lower()
                bid = fl(m["yes_bid_dollars"]); ask = fl(m["yes_ask_dollars"]); mid = (bid + ask) / 2
                for g in pin:
                    for team, prob in g["probs"].items():
                        t = team.lower()
                        if t and (t in title or any(w in title for w in t.split() if len(w) > 3)):
                            dev = prob - mid
                            hurdle = (ask - bid) / 2 + taker_fee(ask)
                            devs.append((abs(dev), dev, hurdle, m["ticker"]))
                            break
    if devs:
        big = [d for d in devs if d[0] > d[2]]
        print(f"  matched {len(devs)} sides; mean |Kalshi-Pinnacle dev| = "
              f"{statistics.mean(d[0] for d in devs)*100:.2f}c; "
              f"sides clearing spread+fee hurdle = {len(big)} ({100*len(big)/len(devs):.0f}%)")
        print("  NOTE: snapshot != proof. CLV over weeks is the honest test.")


def main():
    rows = kalshi_self_backtest(max_games=120)
    lag_harness_note()


if __name__ == "__main__":
    main()
