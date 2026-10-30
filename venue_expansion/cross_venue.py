#!/usr/bin/env python3
"""cross_venue.py -- executes venue_expansion/CROSS_VENUE_SPEC.md (registered 2026-10-30).  No bar here may move.

QUESTION.  Does  kalshi_yes_ask + kalshi_fee + sportsbook_implied_prob(opposing side)  ever sum to < 1.00?

SUBCOMMANDS
  collect  --minutes M --cadence S   paired Kalshi + Action Network pulls, appended to cache/cross_venue/snapshots.jsonl.gz
  analyze                            score the cached snapshots -> out/cross_venue.json + out/cross_venue.md
  selftest                           fee table, odds conversion, simultaneity guard, AST audit + negative controls

FROZEN READINGS (fixed before any snapshot was scored; see also the spec)
  * VERDICT UNIVERSE = KXNFLGAME (the spec's universe).  NBA / NHL / NCAAF game winners are collected and scored as a
    SECONDARY, labelled disclosure; they cannot move the verdict.
  * EXECUTABLE BOOKS.  Action Network book_id 15 is "Consensus" and 30 is "Open" (the opening line): neither is a
    sportsbook one can bet.  The spec's "7 distinct book_ids" therefore contains 5 real books (49 Caesars, 68 DraftKings,
    69 FanDuel, 71 BetRivers, 75 BetMGM).  Verdict is computed on the 5 executable books (PRIMARY).  The spec-literal
    7-id variant, and ids 15/30 on their own, are reported alongside.  Book names come from GET /web/v1/books.
  * Edge = 1.00 - cost, in percentage points of the $1 payout (the stricter reading).  edge/cost (return on stake) is
    reported next to it; the bar is applied to 1.00 - cost.
  * INSTANCE = a distinct (game, book, pairing) EPISODE: a maximal run of consecutive snapshots in which cost < 1.00.
    Edge / size of an episode are those at its FIRST snapshot (the moment one could first have acted).  Raw
    snapshot-level counts are reported next to it.
  * Dollar size = Kalshi leg notional = yes_ask_size (contracts) x yes_ask.  Two-leg outlay (size x cost) and profit
    (size x edge) are also reported; the PASS bar (median >= $100) is applied to the Kalshi-leg notional, and the
    two-leg outlay variant is reported beside it.
  * Fee = ceil(7 * fee_multiplier * p * (1-p)) cents per contract at the crossing ask (per the spec; real Kalshi
    rounds a whole order, so for size > 1 this is conservative).  fee_type / fee_multiplier are read from each series.
  * Survival: first snapshot whose reference time is >= 60 s after the episode's first snapshot (and <= 90 s after);
    the same (game, book, pairing) must still have cost < 1.00.  Episodes with no such snapshot are CENSORED, not
    counted either way.  The rate is survivors / (survivors + failures).
  * Simultaneity: a pair is used only if (latest leg end) - (earliest leg start) <= 60 s.
"""
import argparse
import ast
import datetime as dt
import gzip
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "cross_venue")
OUT = os.path.join(HERE, "out")
SNAP = os.path.join(CACHE, "snapshots.jsonl.gz")
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
AN = "https://api.actionnetwork.com/web"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# league -> (kalshi series, action-network slug, role)
LEAGUES = {
    "nfl": ("KXNFLGAME", "nfl", "VERDICT"),
    "nba": ("KXNBAGAME", "nba", "secondary"),
    "nhl": ("KXNHLGAME", "nhl", "secondary"),
    "ncaaf": ("KXNCAAFGAME", "ncaaf", "secondary"),
}
VERDICT_LEAGUE = "nfl"
EXEC_BOOKS = (49, 68, 69, 71, 75)
PSEUDO_BOOKS = (15, 30)
BOOK_NAMES = {15: "Consensus", 30: "Open", 49: "Caesars", 68: "DraftKings", 69: "FanDuel", 71: "BetRivers", 75: "BetMGM"}
SIM_LIMIT_S = 60.0
RECHECK_MIN_S, RECHECK_MAX_S = 60.0, 90.0

# frozen PASS / KILL bars (spec, 2026-10-30)
BAR_N, BAR_GAMES, BAR_EDGE_PCT, BAR_SIZE_USD, BAR_BOOK_SHARE, BAR_SURVIVE, KILL_SURVIVE = 20, 10, 1.0, 100.0, 0.50, 0.50, 0.10


# ----------------------------------------------------------------------------------------------- pure functions
def fee_cents(price_cents, multiplier=1):
    """ceil(7 * mult * p * (1-p)) cents per contract, exact (Fractions).  price in integer cents."""
    x = Fraction(7) * Fraction(multiplier).limit_denominator(1000) * price_cents * (100 - price_cents) / 10000
    return math.ceil(x)


def implied(american):
    """American odds -> implied probability, frozen conversion, no de-vigging."""
    o = int(american)
    if o >= 0:
        return Fraction(100, o + 100)
    return Fraction(-o, -o + 100)


def pair_ok(leg_starts, leg_ends):
    """Simultaneity rule: every leg must have been fetched inside one SIM_LIMIT_S window."""
    return (max(leg_ends) - min(leg_starts)) <= SIM_LIMIT_S


def cost_of(ask_dollars, book_odds_other_side, mult):
    """Total cost of $1 payout: kalshi ask + fee + book implied prob of the opposing side.  Returns (cost, fee_c)."""
    ask_c = int(round(float(ask_dollars) * 100))
    f = fee_cents(ask_c, mult)
    return Fraction(ask_c, 100) + Fraction(f, 100) + implied(book_odds_other_side), f


# ------------------------------------------------------------------------------------------------ http
def http_json(url, retries=2, timeout=20):
    err = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa
            err = repr(e)
            time.sleep(1.0 + i)
    raise RuntimeError(err)


def fetch_kalshi(series):
    t0 = time.time()
    markets, cursor, pages = [], "", 0
    while True:
        url = f"{KALSHI}/markets?series_ticker={series}&status=open&limit=200" + (f"&cursor={cursor}" if cursor else "")
        d = http_json(url)
        pages += 1
        for m in d.get("markets", []):
            markets.append({  # ask-side fields only; long rule text dropped
                "tk": m["ticker"], "ev": m["event_ticker"], "nm": m.get("yes_sub_title"),
                "ask": m.get("yes_ask_dollars"), "asz": m.get("yes_ask_size_fp"), "st": m.get("status"),
                "occ": m.get("occurrence_datetime"), "cl": m.get("close_time")})
        cursor = d.get("cursor") or ""
        if not cursor or pages >= 12:
            break
    return {"t_start": t0, "t_end": time.time(), "pages": pages, "markets": markets}


def fetch_an(slug):
    t0 = time.time()
    d = http_json(f"{AN}/v2/scoreboard/{slug}")
    games = []
    for g in d.get("games", []):
        ml = []
        for b, m in (g.get("markets") or {}).items():
            for x in (m.get("event") or {}).get("moneyline", []) or []:
                if x.get("period", "event") != "event" or x.get("is_alt_market"):
                    continue
                ml.append({"b": int(x.get("book_id", b)), "side": x.get("side"), "tid": x.get("team_id"),
                           "odds": x.get("odds"), "ls": x.get("line_status"), "live": x.get("is_live")})
        games.append({"id": g["id"], "status": g.get("status"), "start": g.get("start_time"),
                      "home": g.get("home_team_id"), "away": g.get("away_team_id"),
                      "teams": {str(t["id"]): {"full": t.get("full_name"), "loc": t.get("location"),
                                                "disp": t.get("display_name"), "abbr": t.get("abbr")}
                                for t in g.get("teams", [])},
                      "ml": ml})
    return {"t_start": t0, "t_end": time.time(), "games": games}


def fetch_series_records():
    out = {}
    for lg, (series, _, _) in LEAGUES.items():
        s = http_json(f"{KALSHI}/series/{series}")["series"]
        out[lg] = {"series": series, "fee_type": s.get("fee_type"), "fee_multiplier": s.get("fee_multiplier"),
                   "last_updated_ts": s.get("last_updated_ts"), "title": s.get("title")}
    return out


# ------------------------------------------------------------------------------------------------ collect
def collect(minutes, cadence):
    os.makedirs(CACHE, exist_ok=True)
    recs = fetch_series_records()
    with open(os.path.join(CACHE, "series_records.json"), "w") as f:
        json.dump({"fetched": time.time(), "records": recs}, f, indent=1)
    try:
        books = http_json(f"{AN}/v1/books")["books"]
        with open(os.path.join(CACHE, "an_books.json"), "w") as f:
            json.dump([b for b in books if b["id"] in BOOK_NAMES], f, indent=1)
    except Exception as e:  # noqa
        print("books fetch failed", e)
    t_begin = time.time()
    n = 0
    print(f"collect start {dt.datetime.utcnow().isoformat()}Z minutes={minutes} cadence={cadence}", flush=True)
    while True:
        t_slot = t_begin + n * cadence
        if t_slot > t_begin + minutes * 60:
            break
        wait = t_slot - time.time()
        if wait > 0:
            time.sleep(wait)
        snap = {"snap": n, "t_wall": time.time(), "leagues": {}}
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {}
            for lg, (series, slug, _) in LEAGUES.items():
                futs[(lg, "kalshi")] = ex.submit(fetch_kalshi, series)
                futs[(lg, "an")] = ex.submit(fetch_an, slug)
            for (lg, leg), fu in futs.items():
                try:
                    r = fu.result()
                except Exception as e:  # noqa
                    r = {"error": repr(e)[:200]}
                snap["leagues"].setdefault(lg, {})[leg] = r
        line = (json.dumps(snap, separators=(",", ":")) + "\n").encode()
        with open(SNAP, "ab") as f:
            f.write(gzip.compress(line))
        n += 1
        if n % 10 == 1:
            nf = snap["leagues"].get("nfl", {})
            print(f"snap {n} at {dt.datetime.utcnow().strftime('%H:%M:%S')}Z nfl kalshi mkts="
                  f"{len(nf.get('kalshi', {}).get('markets', []))} an games={len(nf.get('an', {}).get('games', []))}", flush=True)
    print(f"collect done snapshots={n}", flush=True)


# ------------------------------------------------------------------------------------------------ matching
def norm(s):
    s = (s or "").lower().replace("&", " and ").replace(".", " ").replace("'", "").replace("’", "")
    s = re.sub(r"\bst\b", "state", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def team_keys(t):
    ks = set()
    loc, disp = t.get("loc") or "", t.get("disp") or ""
    if loc:
        nl = "los angeles" if norm(loc) == "la" else norm(loc)   # Action Network lists the Clippers' location as "LA"
        ks.add(nl)
        if disp:
            ks.add(norm(nl + " " + disp[0]))
    return ks


def match_event(ev_markets, games):
    """Return (game, {market_ticker: team_id}) or (None, reason).  Both Kalshi names must resolve to the two AN teams."""
    names = [m["nm"] for m in ev_markets]
    cands = []
    for g in games:
        tmap = {}
        for tid, t in g["teams"].items():
            for k in team_keys(t):
                tmap.setdefault(k, []).append(tid)
        res = {}
        for m in ev_markets:
            hit = tmap.get(norm(m["nm"]), [])
            if len(hit) == 1:
                res[m["tk"]] = int(hit[0])
        if len(res) == 2 and len(set(res.values())) == 2:
            cands.append((g, res))
    if len(cands) == 1:
        return cands[0]
    return None, ("no_AN_game_with_both_names" if not cands else "ambiguous_multiple_AN_games")


def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:  # noqa
        return None


# ------------------------------------------------------------------------------------------------ scoring
def read_snapshots():
    out = []
    if not os.path.exists(SNAP):
        return out
    with gzip.open(SNAP, "rt") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:  # noqa
                    pass
    return out


def score_snapshot(snap, recs, excl, matched_log):
    """Return list of pair rows for one snapshot.  excl: dict reason->count (per-observation exclusions)."""
    rows = []

    def ex(reason, k=1):
        excl[reason] = excl.get(reason, 0) + k

    for lg, legs in snap["leagues"].items():
        k, a = legs.get("kalshi", {}), legs.get("an", {})
        if "error" in k or "error" in a or "markets" not in k or "games" not in a:
            ex(f"{lg}:leg_fetch_error_snapshot_discarded")
            continue
        if not pair_ok([k["t_start"], a["t_start"]], [k["t_end"], a["t_end"]]):
            ex(f"{lg}:simultaneity_gt_60s_pair_discarded")
            continue
        rec = recs.get(lg, {})
        if rec.get("fee_type") != "quadratic_with_maker_fees" or rec.get("fee_multiplier") is None:
            ex(f"{lg}:unknown_fee_type_{rec.get('fee_type')}", len(k["markets"]))
            continue
        mult = rec["fee_multiplier"]
        t_ref = max(k["t_end"], a["t_end"])
        span = t_ref - min(k["t_start"], a["t_start"])
        games = [g for g in a["games"] if g["status"] == "scheduled" and parse_iso(g["start"] or "") and parse_iso(g["start"]) > t_ref]
        ex(f"{lg}:AN_game_not_pregame(status!=scheduled or started)", len(a["games"]) - len(games))
        evs = {}
        for m in k["markets"]:
            evs.setdefault(m["ev"], []).append(m)
        for evt, ms in evs.items():
            if len(ms) != 2:
                ex(f"{lg}:kalshi_event_without_exactly_2_markets", 1)
                continue
            g, res = match_event(ms, games)
            if g is None:
                ex(f"{lg}:kalshi_event_unmatched:{res}")
                matched_log.setdefault(lg, {}).setdefault("unmatched_events", {})[evt] = res
                continue
            occ, st = parse_iso(ms[0]["occ"] or ""), parse_iso(g["start"])
            # Kalshi occurrence_datetime is reliable only for NFL (verified start+3h); NCAAF carries a 03:00Z placeholder.
            if lg == VERDICT_LEAGUE and occ is not None and not (st - 3600 <= occ <= st + 8 * 3600):
                ex(f"{lg}:kalshi_event_time_mismatch_vs_AN_start")
                continue
            matched_log.setdefault(lg, {}).setdefault("matched_events", {})[evt] = g["id"]
            tid_home, tid_away = g["home"], g["away"]
            mk_of = {tid: m for m in ms for tm, tid in res.items() if tm == m["tk"]}
            if tid_home not in mk_of or tid_away not in mk_of:
                ex(f"{lg}:AN_home_away_ids_not_in_teams")
                continue
            by_book = {}
            for x in g["ml"]:
                by_book.setdefault(x["b"], []).append(x)
            for b, xs in by_book.items():
                bad = None
                side = {}
                for x in xs:
                    if x["tid"] not in (tid_home, tid_away):
                        bad = "book_team_id_not_in_game"
                    elif (x["side"] == "home") != (x["tid"] == tid_home):
                        bad = "book_side_label_inconsistent_with_team_id"
                    if x["ls"] not in (None, "normal"):
                        bad = bad or f"line_status_{x['ls']}"
                    if x["live"]:
                        bad = bad or "book_line_is_live"
                    if not isinstance(x["odds"], int) or abs(x["odds"]) < 100:
                        bad = bad or "odds_invalid"
                    side[x["tid"]] = x["odds"]
                if bad or len(side) != 2:
                    ex(f"{lg}:book{b}_excluded:{bad or 'missing_a_side'}")
                    continue
                for kal_tid, oth_tid, label in ((tid_home, tid_away, "kalshi_home+book_away"),
                                                (tid_away, tid_home, "kalshi_away+book_home")):
                    m = mk_of[kal_tid]
                    try:
                        ask, asz = float(m["ask"]), float(m["asz"])
                    except Exception:  # noqa
                        ex(f"{lg}:kalshi_ask_missing_or_unparseable")
                        continue
                    if not (0.0 < ask < 1.0):
                        ex(f"{lg}:kalshi_ask_not_in_(0,1)_no_executable_ask")
                        continue
                    if asz <= 0:
                        ex(f"{lg}:kalshi_ask_size_zero")
                        continue
                    cost, f = cost_of(m["ask"], side[oth_tid], mult)
                    gap = 1 - cost
                    rows.append({"lg": lg, "snap": snap["snap"], "t": t_ref, "span": span, "ev": evt, "game": g["id"],
                                 "book": b, "pair": label, "ask": ask, "asz": asz, "fee_c": f, "odds": side[oth_tid],
                                 "p_book": float(implied(side[oth_tid])), "cost": float(cost), "gap": float(gap),
                                 "gap_exact": [gap.numerator, gap.denominator], "arb": cost < 1,
                                 "teams": " vs ".join(t["full"] for t in g["teams"].values())})
    return rows


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def dist(xs):
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "min": min(xs), "p1": pct(xs, .01), "p5": pct(xs, .05), "p25": pct(xs, .25),
            "median": statistics.median(xs), "p75": pct(xs, .75), "p95": pct(xs, .95), "p99": pct(xs, .99), "max": max(xs)}


HIST_EDGES = [-100, -15, -10, -8, -6, -5, -4, -3, -2, -1, 0, 1, 2, 5, 100]  # gap in percentage points


def histogram(gaps_pp):
    out = []
    for lo, hi in zip(HIST_EDGES[:-1], HIST_EDGES[1:]):
        out.append({"bin": f"[{lo},{hi})", "n": sum(1 for g in gaps_pp if lo <= g < hi)})
    return out


def episodes(rows):
    """Group arb rows into (game, book, pair) episodes over consecutive snapshots of the same league."""
    by = {}
    for r in rows:
        by.setdefault((r["lg"], r["game"], r["book"], r["pair"]), []).append(r)
    return by


def analyze_universe(rows_all, snaps_by_lg, label, books):
    """rows_all: all pair rows for ONE league; books: allowed book ids.  Returns result dict."""
    rows = [r for r in rows_all if r["book"] in books]
    res = {"label": label, "books": list(books), "n_pair_observations": len(rows)}
    gaps = [r["gap"] * 100 for r in rows]
    res["gap_pp_all_observations"] = dist(gaps)
    res["gap_hist"] = histogram(gaps)
    res["near_miss_counts_obs"] = {f"gap>={t}pp": sum(1 for g in gaps if g >= t) for t in (0, -0.5, -1, -2, -3, -4)}
    # best gap per (game, book, pair) over the window
    best = {}
    for r in rows:
        key = (r["game"], r["book"], r["pair"])
        if key not in best or r["gap"] > best[key]["gap"]:
            best[key] = r
    bg = [v["gap"] * 100 for v in best.values()]
    res["gap_pp_best_per_game_book_pair"] = dist(bg)
    res["gap_hist_best_per_game_book_pair"] = histogram(bg)
    res["near_miss_counts_best_triples"] = {f"gap>={t}pp": sum(1 for g in bg if g >= t) for t in (0, -0.5, -1, -2, -3, -4)}
    bgm = {}
    for r in rows:
        if r["game"] not in bgm or r["gap"] > bgm[r["game"]]["gap"]:
            bgm[r["game"]] = r
    res["best_gap_per_game_any_book"] = sorted(
        [{"game": r["teams"], "book": BOOK_NAMES.get(r["book"], r["book"]), "pair": r["pair"], "gap_pp": round(r["gap"] * 100, 3),
          "ask": r["ask"], "fee_c": r["fee_c"], "odds": r["odds"], "ask_size": r["asz"]} for r in bgm.values()],
        key=lambda x: -x["gap_pp"])
    res["top_near_misses_best_triples"] = [
        {"game": v["teams"], "book": BOOK_NAMES.get(v["book"], v["book"]), "pair": v["pair"], "gap_pp": round(v["gap"] * 100, 3),
         "ask": v["ask"], "fee_c": v["fee_c"], "book_odds_other_side": v["odds"], "p_book": round(v["p_book"], 4),
         "ask_size": v["asz"], "snap": v["snap"]} for v in sorted(best.values(), key=lambda v: -v["gap"])[:25]]
    # --- arbitrage instances
    arb_rows = [r for r in rows if r["arb"]]
    res["n_arb_snapshot_observations"] = len(arb_rows)
    eps = []
    for key, rs in episodes(arb_rows).items():
        rs.sort(key=lambda r: r["snap"])
        cur = [rs[0]]
        runs = []
        for r in rs[1:]:
            if r["snap"] == cur[-1]["snap"] + 1:
                cur.append(r)
            else:
                runs.append(cur)
                cur = [r]
        runs.append(cur)
        eps.extend(runs)
    snaps_idx = {s["snap"]: s for s in snaps_by_lg}
    ref_t = {s["snap"]: s["t"] for s in snaps_by_lg}
    rows_by_snap_key = {}
    for r in rows:
        rows_by_snap_key[(r["snap"], r["game"], r["book"], r["pair"])] = r
    ep_out = []
    for run in eps:
        f = run[0]
        t0 = f["t"]
        # recheck snapshot
        rj = None
        for sn in sorted(ref_t):
            if sn > f["snap"] and RECHECK_MIN_S <= ref_t[sn] - t0 <= RECHECK_MAX_S:
                rj = sn
                break
        if rj is None:
            surv = "censored"
        else:
            rr = rows_by_snap_key.get((rj, f["game"], f["book"], f["pair"]))
            if rr is None:
                surv = "fail_gone"      # game started / book pulled / market closed
            else:
                surv = "survive" if rr["arb"] else "fail_closed"
        ep_out.append({"game": f["teams"], "game_id": f["game"], "book": BOOK_NAMES.get(f["book"], f["book"]), "book_id": f["book"],
                       "pair": f["pair"], "first_snap": f["snap"], "n_snaps": len(run), "duration_s": run[-1]["t"] - f["t"],
                       "ask": f["ask"], "fee_c": f["fee_c"], "book_odds_other_side": f["odds"], "p_book": round(f["p_book"], 5),
                       "cost": round(f["cost"], 5), "edge_pp": round(f["gap"] * 100, 4),
                       "edge_pct_of_stake": round(f["gap"] / f["cost"] * 100, 4),
                       "ask_size_contracts": f["asz"], "kalshi_leg_usd": round(f["asz"] * f["ask"], 2),
                       "two_leg_outlay_usd": round(f["asz"] * f["cost"], 2), "profit_usd": round(f["asz"] * f["gap"], 2),
                       "book_stake_needed_usd": round(f["asz"] * f["p_book"], 2),
                       "best_edge_pp_in_run": round(max(r["gap"] for r in run) * 100, 4), "recheck": surv,
                       "recheck_snap": rj})
    ep_out.sort(key=lambda e: -e["edge_pp"])
    res["episodes"] = ep_out
    n = len(ep_out)
    res["n_arb_episodes"] = n
    res["n_distinct_games"] = len({e["game_id"] for e in ep_out})
    res["n_distinct_triples"] = len({(e["game_id"], e["book_id"], e["pair"]) for e in ep_out})
    if n:
        res["median_edge_pp"] = statistics.median(e["edge_pp"] for e in ep_out)
        res["median_edge_pct_of_stake"] = statistics.median(e["edge_pct_of_stake"] for e in ep_out)
        res["median_kalshi_leg_usd"] = statistics.median(e["kalshi_leg_usd"] for e in ep_out)
        res["median_two_leg_outlay_usd"] = statistics.median(e["two_leg_outlay_usd"] for e in ep_out)
        res["median_profit_usd"] = statistics.median(e["profit_usd"] for e in ep_out)
        res["total_profit_usd_if_all_taken"] = round(sum(e["profit_usd"] for e in ep_out), 2)
        bc, gc = {}, {}
        for e in ep_out:
            bc[e["book"]] = bc.get(e["book"], 0) + 1
            gc[e["game"]] = gc.get(e["game"], 0) + 1
        res["by_book"] = bc
        res["by_game"] = dict(sorted(gc.items(), key=lambda kv: -kv[1]))
        res["max_book_share"] = max(bc.values()) / n
        res["max_game_share"] = max(gc.values()) / n
    sv = sum(1 for e in ep_out if e["recheck"] == "survive")
    fl = sum(1 for e in ep_out if e["recheck"].startswith("fail"))
    res["recheck"] = {"survive": sv, "fail_closed": sum(1 for e in ep_out if e["recheck"] == "fail_closed"),
                      "fail_gone": sum(1 for e in ep_out if e["recheck"] == "fail_gone"),
                      "censored": sum(1 for e in ep_out if e["recheck"] == "censored"),
                      "survival_rate": (sv / (sv + fl)) if (sv + fl) else None}
    # snapshot-level survival: every arb observation that has a recheck snapshot
    s_sv = s_fl = 0
    for r in arb_rows:
        rj = None
        for sn in sorted(ref_t):
            if sn > r["snap"] and RECHECK_MIN_S <= ref_t[sn] - r["t"] <= RECHECK_MAX_S:
                rj = sn
                break
        if rj is None:
            continue
        rr = rows_by_snap_key.get((rj, r["game"], r["book"], r["pair"]))
        if rr is not None and rr["arb"]:
            s_sv += 1
        else:
            s_fl += 1
    res["recheck_snapshot_level"] = {"survive": s_sv, "fail": s_fl, "rate": (s_sv / (s_sv + s_fl)) if (s_sv + s_fl) else None}
    return res


def verdict(res):
    """Frozen PASS / KILL rule, verbatim.  Returns (verdict, table)."""
    n = res["n_arb_episodes"]
    bars = []
    surv = res["recheck"]["survival_rate"]
    bars.append(("1a >= 20 fee-inclusive instances", BAR_N, n, n >= BAR_N))
    bars.append(("1b across >= 10 distinct games", BAR_GAMES, res["n_distinct_games"], res["n_distinct_games"] >= BAR_GAMES))
    med_e = res.get("median_edge_pp")
    bars.append(("2 median arb >= 1.0% (1.00 - cost, pp)", BAR_EDGE_PCT, med_e, med_e is not None and med_e >= BAR_EDGE_PCT))
    med_s = res.get("median_kalshi_leg_usd")
    bars.append(("3 median executable size >= $100 (Kalshi leg notional)", BAR_SIZE_USD, med_s, med_s is not None and med_s >= BAR_SIZE_USD))
    mb = res.get("max_book_share")
    bars.append(("4 no single book > 50%", BAR_BOOK_SHARE, mb, mb is not None and mb <= BAR_BOOK_SHARE))
    bars.append(("5 >= 50% survive 60 s re-check", BAR_SURVIVE, surv, surv is not None and surv >= BAR_SURVIVE))
    if all(b[3] for b in bars):
        v = "PASS"
    elif n == 0 or (surv is not None and surv < KILL_SURVIVE):
        v = "KILL"
    else:
        v = "INSUFFICIENT"
    return v, [{"bar": b[0], "frozen_threshold": b[1], "observed": b[2], "met": bool(b[3])} for b in bars]


# ------------------------------------------------------------------------------------------------ audit (anchor c)
class AuditError(Exception):
    pass


_W = lambda *p: "".join(p)  # noqa: E731  (assembled so this file's own text never spells the forbidden words)
_FORBIDDEN_TOKENS = {_W("b", "id"), _W("b", "ids"), _W("m", "id"), _W("m", "ids"), _W("m", "id", "point"), _W("m", "id", "price"),
                     _W("m", "id", "quote")}


def _tokens(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s)
    return {t.lower() for t in re.split(r"[^A-Za-z]+", s) if t}


def audit_executable_only(source):
    """AST scan: raise AuditError if the code names, reads or computes a bid or a mid.  Docstrings are ignored."""
    tree = ast.parse(source)
    doc_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) and isinstance(b[0].value.value, str):
                doc_ids.add(id(b[0].value))
    problems = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            names.append(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_ids:
            names.append(node.value)
        for nm in names:
            hit = _tokens(nm) & _FORBIDDEN_TOKENS
            if hit:
                problems.append(f"line {getattr(node, 'lineno', '?')}: forbidden token {sorted(hit)} in {nm[:40]!r}")
        # arithmetic-mean-of-two pattern: (x + y) / 2  or  (x + y) * 0.5
        if isinstance(node, ast.BinOp):
            two = lambda c: isinstance(c, ast.Constant) and c.value in (2, 2.0)  # noqa: E731
            half = lambda c: isinstance(c, ast.Constant) and c.value == 0.5  # noqa: E731
            addish = lambda c: isinstance(c, ast.BinOp) and isinstance(c.op, ast.Add) or (  # noqa: E731
                isinstance(c, ast.Call) and getattr(c.func, "id", "") == "sum")
            if isinstance(node.op, (ast.Div, ast.FloorDiv)) and two(node.right) and addish(node.left):
                problems.append(f"line {node.lineno}: (a+b)/2 pattern")
            if isinstance(node.op, ast.Mult) and ((half(node.right) and addish(node.left)) or (half(node.left) and addish(node.right))):
                problems.append(f"line {node.lineno}: (a+b)*0.5 pattern")
    if problems:
        raise AuditError("; ".join(problems))
    return True


def run_audit():
    src = open(os.path.abspath(__file__)).read()
    out = {"clean_source_passes": False, "negative_controls": []}
    audit_executable_only(src)
    out["clean_source_passes"] = True
    _XB, _XM = _W("b", "id"), _W("m", "id")
    doctored = {
        "control_1_mean_of_two_quotes_named": src + f"\n{_XM}_price = (yes_{_XB} + yes_ask) / 2\n",
        "control_2_bare_average_pattern": src + "\n_x = (a_price + b_price) / 2\n",
        "control_3_reads_the_low_side_field": src + f"\n_p = m['yes_{_XB}_dollars']\n",
        "control_4_half_multiplication": src + "\n_x = (a_price + b_price) * 0.5\n",
    }
    for name, s in doctored.items():
        try:
            audit_executable_only(s)
            out["negative_controls"].append({"control": name, "raised": False})
        except AuditError as e:
            out["negative_controls"].append({"control": name, "raised": True, "message": str(e)[:160]})
    if not all(c["raised"] for c in out["negative_controls"]):
        raise AssertionError("negative control FAILED to raise: " + json.dumps(out["negative_controls"]))
    return out


def run_selftest():
    t = {}
    # fee table from the spec
    t["fee_table"] = {c: fee_cents(c) for c in (50, 70, 85, 95, 1, 99)}
    assert (t["fee_table"][50], t["fee_table"][70], t["fee_table"][85], t["fee_table"][95]) == (2, 2, 1, 1), t["fee_table"]
    assert fee_cents(50, 0.5) == 1 and fee_cents(50, 1) == 2
    # odds conversion
    assert implied(100) == Fraction(1, 2) and implied(-110) == Fraction(110, 210) and implied(150) == Fraction(2, 5) and implied(-200) == Fraction(2, 3)
    t["odds_conversion"] = "ok"
    # arb arithmetic: known arb and known non-arb
    c, f = cost_of("0.40", 130, 1)   # .40 + 2c + .4348 = .8548 -> arb
    assert c < 1 and f == 2
    c2, _ = cost_of("0.55", -150, 1)  # .55+.02+.60 = 1.17 -> not
    assert c2 > 1
    t["arb_arithmetic"] = "ok"
    # simultaneity guard
    assert pair_ok([100.0, 100.5], [101.0, 101.2]) is True
    assert pair_ok([100.0, 100.5], [101.0, 161.5]) is False
    snap = {"snap": 0, "leagues": {"nfl": {"kalshi": {"t_start": 0, "t_end": 1, "markets": []},
                                           "an": {"t_start": 61.5, "t_end": 62, "games": []}}}}
    excl = {}
    rows = score_snapshot(snap, {"nfl": {"fee_type": "quadratic_with_maker_fees", "fee_multiplier": 1}}, excl, {})
    assert rows == [] and any("simultaneity" in k for k in excl), excl
    t["simultaneity_guard"] = "stale pair (62 s apart) discarded"
    t["audit"] = run_audit()
    return t


# ------------------------------------------------------------------------------------------------ analyze
def analyze():
    audit = run_selftest()
    snaps = read_snapshots()
    recs = json.load(open(os.path.join(CACHE, "series_records.json")))["records"]
    excl, matched_log = {}, {}
    all_rows = []
    for s in snaps:
        all_rows.extend(score_snapshot(s, recs, excl, matched_log))
    by_lg = {}
    for r in all_rows:
        by_lg.setdefault(r["lg"], []).append(r)
    # snapshot reference times per league (only snapshots that produced rows)
    snap_t = {}
    for r in all_rows:
        snap_t.setdefault(r["lg"], {})[r["snap"]] = r["t"]
    ts = [s["t_wall"] for s in snaps]
    spans = [r["span"] for r in all_rows]
    res = {"generated": dt.datetime.utcnow().isoformat() + "Z",
           "window": {"first_snapshot_utc": dt.datetime.utcfromtimestamp(min(ts)).isoformat() + "Z" if ts else None,
                      "last_snapshot_utc": dt.datetime.utcfromtimestamp(max(ts)).isoformat() + "Z" if ts else None,
                      "length_minutes": (max(ts) - min(ts)) / 60 if ts else 0, "n_snapshots_cached": len(snaps),
                      "median_cadence_s": statistics.median([b - a for a, b in zip(ts, ts[1:])]) if len(ts) > 1 else None,
                      "n_snapshots_scored_nfl": len(snap_t.get("nfl", {}))},
           "simultaneity": {"limit_s": SIM_LIMIT_S, "max_pair_span_s_observed": max(spans) if spans else None,
                            "median_pair_span_s_observed": statistics.median(spans) if spans else None,
                            "pairs_discarded": sum(v for k, v in excl.items() if "simultaneity" in k)},
           "fee_provenance": recs,
           "audit_and_selftest": audit,
           "exclusions": dict(sorted(excl.items())),
           "matching": {lg: {"matched_events": len(v.get("matched_events", {})), "unmatched_events": v.get("unmatched_events", {})}
                        for lg, v in matched_log.items()},
           "universes": {}}
    for lg in LEAGUES:
        rl = by_lg.get(lg, [])
        sn = [{"snap": sn_, "t": t_} for sn_, t_ in sorted(snap_t.get(lg, {}).items())]
        res["universes"][lg] = {
            "role": LEAGUES[lg][2],
            "executable_books": analyze_universe(rl, sn, f"{lg} executable books", EXEC_BOOKS),
            "spec_literal_7_ids": analyze_universe(rl, sn, f"{lg} all 7 ids", EXEC_BOOKS + PSEUDO_BOOKS),
            "pseudo_books_only": analyze_universe(rl, sn, f"{lg} Consensus/Open only", PSEUDO_BOOKS),
        }
        for k in ("executable_books", "spec_literal_7_ids"):
            u = res["universes"][lg][k]
            u["verdict"], u["bars"] = verdict(u)
    primary = res["universes"][VERDICT_LEAGUE]["executable_books"]
    res["VERDICT"] = {"universe": "KXNFLGAME x 5 executable books", "verdict": primary["verdict"], "bars": primary["bars"],
                      "spec_literal_7_ids_verdict": res["universes"][VERDICT_LEAGUE]["spec_literal_7_ids"]["verdict"]}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "cross_venue.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    with open(os.path.join(OUT, "cross_venue.md"), "w") as f:
        f.write(render_md(res))
    print(json.dumps(res["VERDICT"], indent=1, default=str))
    return res


def fmt(x, d=3):
    return "n/a" if x is None else (f"{x:.{d}f}" if isinstance(x, float) else str(x))


def render_md(res):
    L = []
    w = res["window"]
    P = res["universes"][VERDICT_LEAGUE]["executable_books"]
    L.append("# Cross-venue arbitrage: Kalshi ask + fee + sportsbook opposing price\n")
    L.append(f"Generated {res['generated']}.  Spec: `CROSS_VENUE_SPEC.md` (registered 2026-10-30).  Code: `cross_venue.py`.  "
             f"Raw snapshots: `cache/cross_venue/snapshots.jsonl.gz` (force-added to git; the cache dir is gitignored).\n")
    L.append(f"**Window:** {w['first_snapshot_utc']} to {w['last_snapshot_utc']} = {fmt(w['length_minutes'], 1)} min, "
             f"{w['n_snapshots_cached']} snapshots cached ({w['n_snapshots_scored_nfl']} scored for NFL), median cadence {fmt(w['median_cadence_s'], 1)} s.  "
             f"Every pre-game line; all games scored were scheduled and not started.\n")
    L.append(f"## VERDICT: **{res['VERDICT']['verdict']}**  (NFL game winners x 5 executable books; spec-literal 7-id variant: "
             f"{res['VERDICT']['spec_literal_7_ids_verdict']})\n")
    L.append("| bar (frozen) | threshold | observed | met |\n|---|---:|---:|:---:|")
    for b in res["VERDICT"]["bars"]:
        L.append(f"| {b['bar']} | {b['frozen_threshold']} | {fmt(b['observed'], 4) if isinstance(b['observed'], float) else b['observed']} | {'yes' if b['met'] else 'NO'} |")
    L.append("")
    L.append("__SUMMARY_PLACEHOLDER__")
    # anchor a
    L.append("## (a) Gap distribution (`100% - combined cost`, percentage points; arb iff > 0)\n")
    L.append("Gap = 1.00 - (Kalshi yes_ask + fee + book implied prob of the opposing side).  Negative = no arb.  "
             "Every pairing of every executable book in every scored snapshot (NFL).\n")
    g = P["gap_pp_all_observations"]
    L.append(f"All observations: n={g.get('n')}  min {fmt(g.get('min'),2)}  p5 {fmt(g.get('p5'),2)}  p25 {fmt(g.get('p25'),2)}  "
             f"**median {fmt(g.get('median'),2)}**  p75 {fmt(g.get('p75'),2)}  p95 {fmt(g.get('p95'),2)}  p99 {fmt(g.get('p99'),2)}  **max {fmt(g.get('max'),2)}**\n")
    L.append("| gap bin (pp) | n observations |\n|---|---:|")
    for h in P["gap_hist"]:
        L.append(f"| {h['bin']} | {h['n']} |")
    L.append("")
    L.append(f"Near-miss counts (observations): {json.dumps(P['near_miss_counts_obs'])}\n")
    g2 = P["gap_pp_best_per_game_book_pair"]
    L.append(f"Best gap each (game, book, pairing) ever reached in the window (n={g2.get('n')}): "
             f"median {fmt(g2.get('median'),2)}, p75 {fmt(g2.get('p75'),2)}, p95 {fmt(g2.get('p95'),2)}, max {fmt(g2.get('max'),2)}.  "
             f"Counts: {json.dumps(P['near_miss_counts_best_triples'])}\n")
    L.append("Top 25 near-misses (best gap per game/book/pairing):\n")
    L.append("| game | book | pairing | gap pp | K ask | fee c | book odds (opp. side) | book p | K ask size |\n|---|---|---|---:|---:|---:|---:|---:|---:|")
    for x in P["top_near_misses_best_triples"]:
        L.append(f"| {x['game']} | {x['book']} | {x['pair']} | {x['gap_pp']} | {x['ask']} | {x['fee_c']} | {x['book_odds_other_side']} | {x['p_book']} | {x['ask_size']} |")
    L.append("")
    L.append("Best gap per game across all executable books:\n")
    L.append("| game | book | pairing | gap pp | ask | fee c | opp. odds | ask size |\n|---|---|---|---:|---:|---:|---:|---:|")
    for x in P["best_gap_per_game_any_book"]:
        L.append(f"| {x['game']} | {x['book']} | {x['pair']} | {x['gap_pp']} | {x['ask']} | {x['fee_c']} | {x['odds']} | {x['ask_size']} |")
    L.append("")
    # instances
    L.append("## Arbitrage instances (fee-inclusive cost < 100%), NFL, executable books\n")
    L.append(f"Episodes (distinct game/book/pairing runs): **{P['n_arb_episodes']}**, across {P['n_distinct_games']} distinct games, "
             f"{P['n_distinct_triples']} distinct game/book/pairing triples; raw snapshot-level arb observations: {P['n_arb_snapshot_observations']}.\n")
    if P["n_arb_episodes"]:
        L.append(f"Median edge {fmt(P['median_edge_pp'],3)} pp of payout ({fmt(P['median_edge_pct_of_stake'],3)}% of stake); median Kalshi-leg size "
                 f"${fmt(P['median_kalshi_leg_usd'],2)}; median two-leg outlay ${fmt(P['median_two_leg_outlay_usd'],2)}; median profit ${fmt(P['median_profit_usd'],2)}; "
                 f"sum of all episodes' profit if every one were filled at its size ${fmt(P['total_profit_usd_if_all_taken'],2)}.\n")
        L.append("| game | book | pairing | K ask | fee c | opp. odds | book p | cost | edge pp | edge % stake | ask size | Kalshi leg $ | two-leg $ | profit $ | book stake needed $ | snaps | 60s re-check |\n"
                 "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for e in P["episodes"]:
            L.append(f"| {e['game']} | {e['book']} | {e['pair']} | {e['ask']} | {e['fee_c']} | {e['book_odds_other_side']} | {e['p_book']} | {e['cost']} | "
                     f"{e['edge_pp']} | {e['edge_pct_of_stake']} | {e['ask_size_contracts']} | {e['kalshi_leg_usd']} | {e['two_leg_outlay_usd']} | {e['profit_usd']} | "
                     f"{e['book_stake_needed_usd']} | {e['n_snaps']} | {e['recheck']} |")
        L.append("")
    rc = P["recheck"]
    L.append(f"## 60-second survival\n\nSurvive {rc['survive']}, fail (arb closed) {rc['fail_closed']}, fail (leg gone) {rc['fail_gone']}, censored (no re-check snapshot in 60-90 s) {rc['censored']}.  "
             f"Episode survival rate: **{fmt(rc['survival_rate'],3)}**.  Snapshot-level: {json.dumps(P['recheck_snapshot_level'])}\n")
    L.append("## Concentration\n")
    L.append(f"By book: {json.dumps(P.get('by_book', {}))} (max share {fmt(P.get('max_book_share'),3)}).  By game: {json.dumps(P.get('by_game', {}))} (max share {fmt(P.get('max_game_share'),3)}).\n")
    # variants
    L.append("## Variants (disclosed, not the verdict)\n")
    L.append("| universe | pair obs | best gap pp | arb episodes | games | median edge pp | median Kalshi $ | survival | verdict |\n|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for lg, u in res["universes"].items():
        for k in ("executable_books", "spec_literal_7_ids", "pseudo_books_only"):
            x = u[k]
            bestg = x["gap_pp_all_observations"].get("max")
            L.append(f"| {lg} / {k} ({u['role']}) | {x['n_pair_observations']} | {fmt(bestg,2)} | {x['n_arb_episodes']} | {x['n_distinct_games']} | "
                     f"{fmt(x.get('median_edge_pp'),3)} | {fmt(x.get('median_kalshi_leg_usd'),1)} | {fmt(x['recheck']['survival_rate'],3)} | {x.get('verdict','-')} |")
    L.append("")
    for lg in ("nba", "nhl", "ncaaf"):
        x = res["universes"][lg]["executable_books"]
        if x["n_arb_episodes"]:
            L.append(f"### {lg} arb episodes (secondary, executable books)\n")
            L.append("| game | book | pairing | K ask | fee c | opp. odds | edge pp | ask size | Kalshi leg $ | profit $ | re-check |\n|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
            for e in x["episodes"][:40]:
                L.append(f"| {e['game']} | {e['book']} | {e['pair']} | {e['ask']} | {e['fee_c']} | {e['book_odds_other_side']} | {e['edge_pp']} | {e['ask_size_contracts']} | {e['kalshi_leg_usd']} | {e['profit_usd']} | {e['recheck']} |")
            L.append("")
    # anchors
    L.append("## (b) Simultaneity\n")
    s = res["simultaneity"]
    L.append(f"Both legs' fetch start/end epoch times are stored in every snapshot.  Rule: discard if (latest leg end - earliest leg start) > {s['limit_s']} s.  "
             f"Observed max span {fmt(s['max_pair_span_s_observed'],2)} s, median {fmt(s['median_pair_span_s_observed'],2)} s; pairs discarded: {s['pairs_discarded']}.  "
             f"The guard is exercised in `selftest` on a synthetic pair 62 s apart (discarded).  Caveat the code cannot see: Action Network's own refresh lag "
             f"versus the books' live prices (the payload carries no per-line timestamp).\n")
    L.append("## (c) Executable prices only: AST audit\n")
    a = res["audit_and_selftest"]["audit"]
    L.append(f"`audit_executable_only` parses `cross_venue.py` and raises on any identifier/attribute/string naming the buy-side-low quote or the average of two quotes (the forbidden words), and on `(a+b)/2` / `(a+b)*0.5` patterns.  "
             f"Clean source passes: **{a['clean_source_passes']}**.  Negative controls (doctored copies; each must raise):\n")
    for c in a["negative_controls"]:
        L.append(f"- `{c['control']}`: raised = **{c['raised']}** ({c.get('message','')})")
    L.append("\nThe collector stores only ask-side Kalshi fields (ticker, event, name, yes_ask, yes_ask_size, status, times).\n")
    L.append("## (d) Fee provenance (from `GET /series/{ticker}` at collection time)\n")
    L.append("| league | series | fee_type | fee_multiplier |\n|---|---|---|---:|")
    for lg, r in res["fee_provenance"].items():
        L.append(f"| {lg} | {r['series']} | {r['fee_type']} | {r['fee_multiplier']} |")
    L.append("\nFee used: `ceil(7 * fee_multiplier * p * (1-p))` cents per contract at the ask, per the spec.  Table check (selftest): "
             f"{json.dumps(res['audit_and_selftest']['fee_table'])}.  Kalshi's real fee is rounded on the whole order, so the per-contract ceiling overstates the fee at size (conservative against finding an arb).\n")
    L.append("## (e) Size in dollars\n\nEvery stage above reports dollars: Kalshi-leg notional (ask size x ask), two-leg outlay (ask size x cost), profit (ask size x edge), "
             "and the sportsbook stake the hedge would need (ask size x book implied probability).  Ask sizes are capped by nothing but the resting Kalshi quote; "
             "the sportsbook leg's own bet limit is unobserved and is typically far below the larger sizes seen here.\n")
    L.append("## Exclusions (count, reason)\n")
    L.append("| count | reason |\n|---:|---|")
    for k, v in res["exclusions"].items():
        if v:
            L.append(f"| {v} | {k} |")
    L.append("\nMatching (events matched / unmatched, final union across snapshots):\n")
    for lg, m in res["matching"].items():
        L.append(f"- {lg}: {m['matched_events']} matched events; unmatched: {json.dumps(m['unmatched_events'])[:1500]}")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "analyze", "selftest"])
    ap.add_argument("--minutes", type=float, default=110)
    ap.add_argument("--cadence", type=float, default=30)
    a = ap.parse_args()
    if a.cmd == "collect":
        collect(a.minutes, a.cadence)
    elif a.cmd == "analyze":
        analyze()
    else:
        print(json.dumps(run_selftest(), indent=1, default=str))


if __name__ == "__main__":
    main()
