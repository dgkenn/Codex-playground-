#!/usr/bin/env python3
"""
KEY TEST harness: does Kalshi sports price LAG a sharp reference (Pinnacle / consensus)?

Logic:
  1. Pull Kalshi live two-sided books per game-event (each event = 2 complementary
     team-win markets). Kalshi YES_team_A and YES_team_B should sum ~1.0.
  2. Compute Kalshi fair prob for each side = de-vigged mid (mid_A / (mid_A+mid_B)),
     and the takeable ASK (what you actually pay to buy YES).
  3. SHARP REFERENCE: de-vigged Pinnacle moneyline (h2h) from the-odds-api.
     - Requires ODDS_API_KEY env var (free tier = 500 req/mo, includes Pinnacle EU).
     - p_fair = (1/dec_A) / (1/dec_A + 1/dec_B)   [two-way de-vig / "balanced book"]
  4. EDGE per side = p_fair_sharp - kalshi_ASK_price.
     A +EV buy needs: p_fair_sharp - ask > taker_fee(ask) + a margin-of-safety.
     Kalshi taker fee = ceil(0.07*P*(1-P)*100)/100 (~1.75c worst case @ 0.50),
     paid ONCE on a buy-and-hold-to-settlement (settlement is free).

Without an ODDS_API_KEY the script runs in SELF-CONSISTENCY mode: it reports Kalshi's
internal overround/hold and spread distribution (the measurable structure today),
and prints exactly what external data is needed to complete the +EV backtest.
"""
import os, sys, time, math, json, datetime, statistics
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ODDS_KEY = os.environ.get("ODDS_API_KEY")
S = requests.Session(); S.headers.update({"Accept": "application/json"})

def fl(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def taker_fee(p):
    """Kalshi taker fee per contract, dollars."""
    if p is None: return None
    return math.ceil(0.07 * p * (1 - p) * 100) / 100

def kget(path, **p):
    for a in range(4):
        try:
            r = S.get(BASE + path, params=p, timeout=20)
            if r.status_code == 200: return r.json()
            if r.status_code == 429: time.sleep(2 ** a); continue
            return {"_err": r.status_code}
        except Exception: time.sleep(2 ** a)
    return {"_err": "fail"}

def kalshi_game_events(series_ticker, limit=60):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    d = kget("/events", series_ticker=series_ticker, status="open",
             limit=limit, with_nested_markets="true")
    evs = []
    for e in d.get("events", []):
        mk = [m for m in e.get("markets", []) if (m.get("close_time") or "") > now]
        if len(mk) == 2:
            evs.append(e)
    return evs

def kalshi_two_sided(event):
    """Return per-event dict: each side -> (mid, bid, ask, devigged_fair)."""
    sides = {}
    for m in event["markets"]:
        yb, ya = fl(m.get("yes_bid_dollars")), fl(m.get("yes_ask_dollars"))
        if yb and ya and 0 < yb < ya < 1:
            sides[m["ticker"]] = {"mid": (yb + ya) / 2, "bid": yb, "ask": ya,
                                  "title": m.get("yes_sub_title") or m.get("title")}
    if len(sides) != 2: return None
    tot = sum(s["mid"] for s in sides.values())
    for s in sides.values():
        s["devig"] = s["mid"] / tot
    return {"overround": tot, "sides": sides}

# ---------------- Sharp reference (Pinnacle via the-odds-api) ----------------
ODDS_SPORT = {"KXMLBGAME": "baseball_mlb", "KXNBA": "basketball_nba",
              "KXNHLGAME": "icehockey_nhl", "KXNFLGAME": "americanfootball_nfl",
              "KXWNBAGAME": "basketball_wnba"}

def pinnacle_h2h(sport_key):
    """Return list of games with de-vigged Pinnacle two-way probs. Needs ODDS_KEY."""
    if not ODDS_KEY: return None
    r = S.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
              params={"apiKey": ODDS_KEY, "regions": "eu", "markets": "h2h",
                      "oddsFormat": "decimal"}, timeout=20)
    if r.status_code != 200:
        print(f"  odds-api {sport_key}: {r.status_code} {r.text[:120]}"); return None
    out = []
    for g in r.json():
        pin = next((b for b in g.get("bookmakers", []) if b["key"] == "pinnacle"), None)
        if not pin: continue
        h2h = next((m for m in pin["markets"] if m["key"] == "h2h"), None)
        if not h2h or len(h2h["outcomes"]) != 2: continue
        o = h2h["outcomes"]
        inv = [1 / x["price"] for x in o]
        tot = sum(inv)
        out.append({"home": g.get("home_team"), "away": g.get("away_team"),
                    "probs": {o[i]["name"]: inv[i] / tot for i in range(2)},
                    "hold": tot - 1})
    return out

def main():
    leagues = ["KXMLBGAME", "KXNBA", "KXNHLGAME", "KXWNBAGAME", "KXNFLGAME"]
    print("=== KALSHI INTERNAL STRUCTURE (measurable today, no external data) ===\n")
    all_overrounds, all_spreads = [], []
    per_league = {}
    for lg in leagues:
        evs = kalshi_game_events(lg)
        ors, sprs = [], []
        for e in evs:
            ts = kalshi_two_sided(e)
            if not ts: continue
            ors.append(ts["overround"])
            for s in ts["sides"].values():
                sprs.append((s["ask"] - s["bid"]) * 100)
        if ors:
            per_league[lg] = {
                "n_games": len(ors),
                "overround_med": round(statistics.median(ors), 4),
                "hold_med_pct": round((statistics.median(ors) - 1) * 100, 2),
                "spread_med_c": round(statistics.median(sprs), 2) if sprs else None,
                "spread_p90_c": round(sorted(sprs)[int(len(sprs)*0.9)], 2) if sprs else None,
            }
            all_overrounds += ors; all_spreads += sprs
            x = per_league[lg]
            print(f"{lg:12s} games={x['n_games']:3d}  "
                  f"hold(mid-sum-1)={x['hold_med_pct']:+5.2f}%  "
                  f"touch_spread med={x['spread_med_c']}c p90={x['spread_p90_c']}c")
    if all_overrounds:
        print(f"\nALL liquid game-markets: median Kalshi mid-overround = "
              f"{statistics.median(all_overrounds):.4f} "
              f"(hold {(statistics.median(all_overrounds)-1)*100:+.2f}%); "
              f"median touch spread {statistics.median(all_spreads):.2f}c")
        print("Interpretation: a ~0% mid-overround means Kalshi's de-vigged fair price = the mid,")
        print("and the real cost to a TAKER is the half-spread + taker fee, not a baked-in vig.")

    # cost to cross + hold to settlement at the 50/50 worst case
    print("\n=== COST TO TAKE (buy YES @ ask, hold to settlement) ===")
    for p in (0.20, 0.50, 0.80):
        half_spread = statistics.median(all_spreads)/2/100 if all_spreads else 0.01
        fee = taker_fee(p)
        print(f"  price~{p:.2f}: half-spread~{half_spread*100:.2f}c + taker fee {fee*100:.2f}c "
              f"= ~{(half_spread+fee)*100:.2f}c hurdle  => need fair-prob edge > {(half_spread+fee)*100:.2f}c")

    # ---------------- The actual edge test (needs sharp ref) ----------------
    print("\n=== KALSHI vs SHARP (Pinnacle) DEVIATION TEST ===")
    if not ODDS_KEY:
        print("  [no ODDS_API_KEY set] -> running SELF-CONSISTENCY only.")
        print("  To complete: set ODDS_API_KEY (the-odds-api free tier, 500 req/mo, incl. Pinnacle).")
        print("  Harness then: for each game, edge_side = pinnacle_devig_prob - kalshi_ask;")
        print("  count +EV signals where edge > half-spread+fee, and (for CLV proof) log entry")
        print("  vs Kalshi settlement price across >=300-500 games over several weeks.")
        return
    print("  Pulling Pinnacle h2h and matching to Kalshi by team...\n")
    n_signals, n_games, edges = 0, 0, []
    for lg in leagues:
        sk = ODDS_SPORT.get(lg)
        if not sk: continue
        pin = pinnacle_h2h(sk)
        if not pin: continue
        evs = kalshi_game_events(lg)
        # naive match: by team substrings present in titles
        for e in evs:
            ts = kalshi_two_sided(e)
            if not ts: continue
            for tk, s in ts["sides"].items():
                title = (s["title"] or "").lower()
                match = None
                for g in pin:
                    for team, prob in g["probs"].items():
                        t = team.lower()
                        if t and (t in title or any(w in title for w in t.split() if len(w) > 3)):
                            match = (team, prob); break
                    if match: break
                if not match: continue
                n_games += 1
                edge = match[1] - s["ask"]           # fair prob minus what you pay
                hurdle = (s["ask"]-s["bid"])/2 + taker_fee(s["ask"])
                edges.append(edge)
                if edge > hurdle:
                    n_signals += 1
                    print(f"  +EV? {tk[:34]:34s} kalshi_ask={s['ask']:.2f} "
                          f"pinn_fair={match[1]:.2f} edge={edge*100:+.1f}c hurdle={hurdle*100:.1f}c")
    if edges:
        print(f"\nMatched {n_games} sides; mean |Kalshi-Pinnacle| dev = "
              f"{statistics.mean(abs(x) for x in edges)*100:.2f}c; "
              f"net +EV signals clearing hurdle = {n_signals}")
        print("NOTE: a single live snapshot is NOT proof. CLV requires logging entry vs settle over weeks.")

if __name__ == "__main__":
    main()
