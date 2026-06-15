#!/usr/bin/env python3
"""
sports_clv_collect.py -- the FORWARD data-collection poller for the Kalshi-vs-sharp
TIMING-LAG test (part B of kalshi_clv_lag.py).

WHAT THIS DOES
--------------
Once per invocation it:
  1. Polls Pinnacle h2h (moneyline) for the in-season liquid leagues via the-odds-api
     (region 'eu' returns Pinnacle), de-vigs each 2-way market to a fair win prob.
  2. For each Pinnacle game, finds the matching OPEN Kalshi game market by team-name
     and records the Kalshi YES mid (the public, no-auth book), so the two prices are
     captured at the SAME wall-clock timestamp.
  3. APPENDS one timestamped row per (game, side) to a CSV. Idempotent-append: it never
     rewrites history, only adds rows; safe to run on a cron forever.

The accrued CSV is the time-series the lag test needs: align d(pinnacle_fair_prob) with
d(kalshi_mid) per game over time and cross-correlate at lags 0..15 min (see
kalshi_clv_lag.py for the analysis side and SPORTS_CLV_SETUP.md for the run-book).

NO-KEY BEHAVIOUR (critical)
---------------------------
If ODDS_API_KEY is absent: print the collection design + quota math and exit 0 cleanly.
Nothing is written, nothing crashes -> the workflow that calls this is safe to merge and
arms itself the moment the operator adds the ODDS_API_KEY repo secret. The free tier is
500 requests/month, so this polls only a few in-season leagues a few times a day.

ENDPOINTS (all public; Kalshi needs no auth, the-odds-api needs the free key)
  the-odds-api:  GET /v4/sports/{sport_key}/odds?regions=eu&markets=h2h&oddsFormat=decimal
  Kalshi:        GET /trade-api/v2/events?series_ticker=...&status=open&with_nested_markets=true

USAGE
  python sports_clv_collect.py [OUT_CSV]
      OUT_CSV defaults to gha_data/sports_clv/sports_clv.csv
"""
import os
import sys
import csv
import time
import datetime

import requests

# --- config -------------------------------------------------------------------
BASE_KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
ODDS_KEY = os.environ.get("ODDS_API_KEY")
DEFAULT_OUT = os.path.join("gha_data", "sports_clv", "sports_clv.csv")

# the-odds-api sport keys keyed by Kalshi game-market series ticker.
# Keep this list SHORT -- each league polled costs ~1 request, and the free tier is
# only 500 requests/month (see quota math in print_design()).
LEAGUE_SPORT = {
    "KXMLBGAME": "baseball_mlb",
    "KXNHLGAME": "icehockey_nhl",
    "KXNBA": "basketball_nba",
    "KXNFLGAME": "americanfootball_nfl",
}

CSV_HEADER = [
    "ts_iso",          # ISO-8601 UTC capture time (the alignment key)
    "ts_epoch",        # unix seconds (numeric alignment key)
    "league",          # Kalshi series ticker, e.g. KXMLBGAME
    "sport_key",       # the-odds-api sport key, e.g. baseball_mlb
    "game_id",         # the-odds-api game id (stable per game)
    "home_team",
    "away_team",
    "team",            # the side this row's prob refers to
    "pinnacle_fair_prob",   # de-vigged Pinnacle win prob for `team` (0..1)
    "pinnacle_hold",        # the vig removed (sum of inverse decimals - 1)
    "kalshi_ticker",        # matched Kalshi market ticker (blank if no match)
    "kalshi_mid",           # matched Kalshi YES mid (blank if no match/quote)
]

S = requests.Session()
S.headers.update({"Accept": "application/json"})


# --- small helpers ------------------------------------------------------------
def fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def kget(path, **params):
    """GET the Kalshi public REST API with retry/backoff. Returns {} on failure."""
    for attempt in range(4):
        try:
            r = S.get(BASE_KALSHI + path, params=params, timeout=25)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            return {}
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return {}


# --- Pinnacle (the sharp line) ------------------------------------------------
def pinnacle_h2h(sport_key):
    """Poll Pinnacle 2-way h2h for one sport_key; de-vig to fair probs.

    Returns a list of dicts: {game_id, home, away, ts, probs:{team:prob}, hold}.
    Returns [] (never raises) on any API/parse error so one bad league can't abort
    the whole run."""
    if not ODDS_KEY:
        return []
    try:
        r = S.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
            params={
                "apiKey": ODDS_KEY,
                "regions": "eu",          # 'eu' is the region that includes Pinnacle
                "markets": "h2h",
                "oddsFormat": "decimal",
            },
            timeout=20,
        )
    except requests.RequestException as e:
        print(f"  odds-api {sport_key}: request error {e}")
        return []
    # surface remaining-quota headers so the operator can watch the 500/mo budget
    rem = r.headers.get("x-requests-remaining")
    used = r.headers.get("x-requests-used")
    if rem is not None:
        print(f"  odds-api {sport_key}: HTTP {r.status_code} (quota used={used} remaining={rem})")
    if r.status_code != 200:
        print(f"  odds-api {sport_key}: {r.status_code} {r.text[:120]}")
        return []
    try:
        games = r.json()
    except ValueError:
        print(f"  odds-api {sport_key}: non-JSON response")
        return []
    out = []
    ts = time.time()
    for g in games:
        pin = next((b for b in g.get("bookmakers", []) if b.get("key") == "pinnacle"), None)
        if not pin:
            continue
        h2h = next((m for m in pin.get("markets", []) if m.get("key") == "h2h"), None)
        if not h2h or len(h2h.get("outcomes", [])) != 2:
            continue
        outc = h2h["outcomes"]
        prices = [fl(o.get("price")) for o in outc]
        if not all(p and p > 1.0 for p in prices):
            continue
        inv = [1.0 / p for p in prices]
        tot = sum(inv)
        out.append({
            "game_id": g.get("id"),
            "home": g.get("home_team"),
            "away": g.get("away_team"),
            "ts": ts,
            "probs": {outc[i]["name"]: inv[i] / tot for i in range(2)},
            "hold": tot - 1.0,
        })
    return out


# --- Kalshi (the market we test for lag) --------------------------------------
def kalshi_open_markets(series):
    """Return open Kalshi game markets for a series with a two-sided YES quote.

    Each entry: {ticker, title, mid}. mid is the YES bid/ask midpoint in dollars."""
    d = kget("/events", series_ticker=series, status="open",
             limit=100, with_nested_markets="true")
    rows = []
    for ev in d.get("events", []):
        for m in ev.get("markets", []):
            bid = fl(m.get("yes_bid_dollars"))
            ask = fl(m.get("yes_ask_dollars"))
            if bid is None or ask is None or not (0 < bid <= ask < 1):
                continue
            title = (m.get("yes_sub_title") or m.get("title") or "")
            rows.append({"ticker": m.get("ticker"), "title": title, "mid": (bid + ask) / 2})
    return rows


def match_kalshi(team, kalshi_rows):
    """Match a Pinnacle team name to a Kalshi YES market by title substring.

    Returns (ticker, mid) or (None, None). Conservative: matches the full team name
    or any distinctive (>3 char) word from it, same heuristic kalshi_clv_lag.py uses."""
    if not team:
        return None, None
    t = team.lower()
    words = [w for w in t.split() if len(w) > 3]
    for row in kalshi_rows:
        title = row["title"].lower()
        if t in title or any(w in title for w in words):
            return row["ticker"], row["mid"]
    return None, None


# --- CSV append ---------------------------------------------------------------
def append_rows(out_csv, rows):
    """Append rows to the CSV, writing the header only if the file is new/empty."""
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    new_file = (not os.path.exists(out_csv)) or os.path.getsize(out_csv) == 0
    with open(out_csv, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(CSV_HEADER)
        for r in rows:
            w.writerow(r)


# --- design / no-key path -----------------------------------------------------
def print_design():
    print("=== sports_clv_collect.py -- FORWARD lag-test data collector ===")
    print("[no ODDS_API_KEY] -> design only, no rows written, exit 0.\n")
    print("WHAT IT COLLECTS (once a key is present):")
    print("  * Pinnacle h2h (the sharp line) per in-season league, de-vigged to a fair prob.")
    print("  * The matching Kalshi YES mid (public book) at the SAME timestamp.")
    print("  * One CSV row per (game, side) appended to gha_data/sports_clv/sports_clv.csv.\n")
    print("WHY: over weeks this accrues the aligned time-series to cross-correlate")
    print("  d(Pinnacle_fair) vs d(Kalshi_mid) at lags 0..15 min. A positive peak at")
    print("  lag>0 means Kalshi FOLLOWS Pinnacle -> a maker resting at post-move fair")
    print("  value (0 fee, +$0.005 LIP rebate) captures the lag. Lag<=0/flat -> no edge.\n")
    print("QUOTA MATH (the-odds-api free tier = 500 requests / month):")
    print(f"  leagues polled per run = {len(LEAGUE_SPORT)} (1 odds request each) = "
          f"{len(LEAGUE_SPORT)} req/run")
    print("  default workflow cron = 3 runs/day (18:00 + 23:00 + 02:00 UTC = US game hours)")
    print(f"  => {len(LEAGUE_SPORT)} x 3 x 30 = {len(LEAGUE_SPORT) * 3 * 30} req/month "
          "(<500 free budget; in-season leagues only return games, off-season ones are ~free).")
    print("  Kalshi requests are public/no-auth and do NOT count against the odds quota.\n")
    print("TO ACTIVATE: add ODDS_API_KEY as a GitHub repo secret (see SPORTS_CLV_SETUP.md).")


# --- main ---------------------------------------------------------------------
def main():
    out_csv = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT

    if not ODDS_KEY:
        print_design()
        return 0

    print(f"=== sports_clv_collect.py -- polling at {now_utc().isoformat()} ===")
    print(f"  output CSV: {out_csv}")
    all_rows = []
    for series, sport_key in LEAGUE_SPORT.items():
        pin_games = pinnacle_h2h(sport_key)
        if not pin_games:
            continue  # off-season / no Pinnacle markets / API hiccup -> skip cleanly
        kalshi_rows = kalshi_open_markets(series)
        captured_ts = now_utc()
        n_before = len(all_rows)
        for g in pin_games:
            for team, prob in g["probs"].items():
                ticker, mid = match_kalshi(team, kalshi_rows)
                all_rows.append([
                    captured_ts.isoformat(),
                    round(captured_ts.timestamp(), 3),
                    series,
                    sport_key,
                    g["game_id"],
                    g["home"],
                    g["away"],
                    team,
                    round(prob, 6),
                    round(g["hold"], 6),
                    ticker or "",
                    "" if mid is None else round(mid, 6),
                ])
        matched = sum(1 for r in all_rows[n_before:] if r[10])
        print(f"  {series} ({sport_key}): {len(pin_games)} Pinnacle games, "
              f"{len(all_rows) - n_before} sides, {matched} matched to Kalshi")

    if not all_rows:
        print("  no in-season Pinnacle markets returned (off-season / quiet window). "
              "Nothing to append.")
        return 0

    append_rows(out_csv, all_rows)
    print(f"  appended {len(all_rows)} rows -> {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
