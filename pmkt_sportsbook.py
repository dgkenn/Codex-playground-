#!/usr/bin/env python3
"""
pmkt_sportsbook.py

Test edge: are Polymarket sports moneyline markets mispriced vs the sharp-ish
de-vigged sportsbook line (ESPN core API -> DraftKings moneyline)?

Truth proxy: de-vigged DraftKings closing moneyline (single book from ESPN;
NOT a Pinnacle/consensus sharp line -- noted in report).

Data:
  ESPN scoreboard   : schedule + final results + team abbrevs
  ESPN core API odds: /events/<id>/competitions/<id>/odds -> DraftKings moneyline
  Polymarket gamma  : /events?slug=mlb-<away>-<home>-<date> -> market, clobTokenIds,
                      live bestBid/bestAsk, settled outcomePrices
  Polymarket CLOB   : /prices-history?market=<tokenId> -> historical pre-game mid

Method:
  For each matched game, P_book (de-vig DK) vs P_poly (PM mid pre-game / live).
  Deviation = P_poly - P_book. Backtest on finals: trade toward the book when
  |deviation|>thr, buy the PM-underpriced side at mid+half_spread, hold to
  resolution. Cluster PnL by day. Brier(book) vs Brier(poly). Also live snapshot.

Author: (this task). Writes report to pmkt_sportsbook_report.md.
"""
import json, requests, datetime, statistics, math, sys, time

S = requests.Session()
S.headers.update({"User-Agent": "research/1.0"})

HALF_SPREAD = 0.005      # measured live MLB spread ~0.01 uniform -> half = 0.005
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
ODDS = "http://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{eid}/competitions/{eid}/odds"
GAMMA_EV = "https://gamma-api.polymarket.com/events"
CLOB_HIST = "https://clob.polymarket.com/prices-history"

# ESPN abbrev -> Polymarket slug abbrev fallbacks (only where they differ)
ABBR_FIX = {"ath": ["ath", "oak"], "chw": ["chw", "cws"], "wsh": ["wsh", "was"],
            "sf": ["sf", "sfg"], "sd": ["sd", "sdp"], "tb": ["tb", "tbr"],
            "kc": ["kc", "kcr"], "la": ["la", "lac"]}


def implied(ml):
    ml = float(ml)
    return (-ml) / (-ml + 100.0) if ml < 0 else 100.0 / (ml + 100.0)


def devig(ml_away, ml_home):
    pa, ph = implied(ml_away), implied(ml_home)
    tot = pa + ph
    return pa / tot, ph / tot   # (P_book_away, P_book_home), vig removed


def parse_ts(s):
    if s is None:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S+00", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    return None


def get_dk_odds(sport, league, eid):
    """Return (away_ml, home_ml, provider) or None."""
    try:
        od = S.get(ODDS.format(sport=sport, league=league, eid=eid), timeout=25).json()
    except Exception:
        return None
    items = od.get("items", [])
    if not items:
        return None
    it = items[0]
    aml = it.get("awayTeamOdds", {}).get("moneyLine")
    hml = it.get("homeTeamOdds", {}).get("moneyLine")
    if aml is None or hml is None:
        return None
    return aml, hml, it.get("provider", {}).get("name", "?")


def nickname_ok(pm_name, espn_name):
    """Conservative name check: PM outcome name should share the last significant
    word (team nickname) with the ESPN display name."""
    pm_name = pm_name.lower(); espn_name = espn_name.lower()
    # last word of each
    a = pm_name.split()[-1]; b = espn_name.split()[-1]
    if a == b:
        return True
    # e.g. 'Red Sox' -> 'sox'; check last-word containment either way
    return a in espn_name or b in pm_name


def get_pm_event(prefix, awab, hmab, date_str):
    """Try slug with abbrev fallbacks. prefix e.g. 'mlb' / 'wnba'."""
    aw_opts = ABBR_FIX.get(awab, [awab])
    hm_opts = ABBR_FIX.get(hmab, [hmab])
    for a in aw_opts:
        for h in hm_opts:
            slug = f"{prefix}-{a}-{h}-{date_str}"
            try:
                d = S.get(GAMMA_EV, params={"slug": slug}, timeout=25).json()
            except Exception:
                continue
            if d and d[0].get("markets"):
                return d[0], slug
    return None, None


def pm_pregame_mid(token, start_dt):
    """Last CLOB mid at or before game start (pre-game price)."""
    try:
        d = S.get(CLOB_HIST, params={"market": token, "interval": "max", "fidelity": 60}, timeout=25).json()
    except Exception:
        return None
    hist = d.get("history", [])
    if not hist:
        return None
    cutoff = start_dt.timestamp() if start_dt else None
    pre = [p for p in hist if cutoff is None or p["t"] <= cutoff]
    if not pre:
        return None
    return float(pre[-1]["p"])


def collect(prefix, sport, league, date_str):
    """Return list of game dicts for one date."""
    ds_compact = date_str.replace("-", "")
    try:
        r = S.get(SCOREBOARD.format(sport=sport, league=league), params={"dates": ds_compact}, timeout=25).json()
    except Exception:
        return []
    out = []
    for e in r.get("events", []):
        comp = e["competitions"][0]
        status = comp["status"]["type"]["name"]
        cs = {c["homeAway"]: c for c in comp["competitors"]}
        if "away" not in cs or "home" not in cs:
            continue
        aw, hm = cs["away"], cs["home"]
        awab = aw["team"]["abbreviation"].lower()
        hmab = hm["team"]["abbreviation"].lower()
        awnm = aw["team"]["displayName"]
        hmnm = hm["team"]["displayName"]
        final = status == "STATUS_FINAL"
        scheduled = status in ("STATUS_SCHEDULED", "STATUS_PRE")
        # skip in-progress: PM reflects live game state, book odds are pregame -> not comparable
        if not final and not scheduled:
            continue
        winner = None
        if final:
            if aw.get("winner"):
                winner = "away"
            elif hm.get("winner"):
                winner = "home"
            else:
                try:
                    sa, sh = float(aw.get("score")), float(hm.get("score"))
                    winner = "away" if sa > sh else "home"
                except Exception:
                    winner = None
        odds = get_dk_odds(sport, league, e["id"])
        if not odds:
            continue
        pb_away, pb_home = devig(odds[0], odds[1])
        pm_ev, slug = get_pm_event(prefix, awab, hmab, date_str)
        if not pm_ev:
            out.append({"matched": False, "game": f"{awab}@{hmab}", "date": date_str, "reason": "no_pm_slug"})
            continue
        m = pm_ev["markets"][0]
        outcomes = json.loads(m.get("outcomes", "[]"))
        if len(outcomes) != 2 or not nickname_ok(outcomes[0], awnm) or not nickname_ok(outcomes[1], hmnm):
            out.append({"matched": False, "game": f"{awab}@{hmab}", "date": date_str, "reason": "name_mismatch"})
            continue
        rec = {"matched": True, "prefix": prefix, "game": f"{awab}@{hmab}", "date": date_str,
               "awnm": awnm, "hmnm": hmnm, "final": final, "winner": winner,
               "provider": odds[2], "ml": (odds[0], odds[1]),
               "pb_away": pb_away, "pb_home": pb_home, "slug": slug,
               "closed": m.get("closed")}
        start_dt = parse_ts(m.get("gameStartTime")) or parse_ts(m.get("endDate"))
        if final:
            toks = json.loads(m.get("clobTokenIds", "[]"))
            if len(toks) != 2:
                rec["matched"] = False; rec["reason"] = "no_tokens"; out.append(rec); continue
            pp_away = pm_pregame_mid(toks[0], start_dt)
            if pp_away is None:
                rec["matched"] = False; rec["reason"] = "no_pm_hist"; out.append(rec); continue
            rec["pp_away"] = pp_away
            rec["pp_home"] = 1.0 - pp_away
            rec["out_away"] = 1 if winner == "away" else 0
            rec["out_home"] = 1 - rec["out_away"] if winner else None
        else:
            bb, ba = m.get("bestBid"), m.get("bestAsk")
            if bb is None or ba is None:
                rec["matched"] = False; rec["reason"] = "no_live_book"; out.append(rec); continue
            rec["bid_away"] = float(bb); rec["ask_away"] = float(ba)
            rec["pp_away"] = (float(bb) + float(ba)) / 2.0  # mid for deviation
            rec["pp_home"] = 1.0 - rec["pp_away"]
        out.append(rec)
    return out


def brier(p, o):
    return (p - o) ** 2


def run_backtest(finals, thresholds=(0.03, 0.05, 0.10)):
    """finals: list of matched final recs with pp_away, pb_away, out_away."""
    # calibration
    bri_book = [brier(f["pb_away"], f["out_away"]) for f in finals]
    bri_poly = [brier(f["pp_away"], f["out_away"]) for f in finals]
    res = {"n_finals": len(finals),
           "brier_book": statistics.mean(bri_book) if bri_book else None,
           "brier_poly": statistics.mean(bri_poly) if bri_poly else None,
           "thresholds": {}}
    for thr in thresholds:
        trades = []   # (day, pnl)
        for f in finals:
            dev_away = f["pp_away"] - f["pb_away"]   # PM minus book on away
            if dev_away < -thr:
                # away underpriced by PM -> buy away
                exec_p = f["pp_away"] + HALF_SPREAD
                pnl = f["out_away"] - exec_p
                trades.append((f["date"], pnl, f["game"], "buy_away", dev_away, exec_p))
            elif dev_away > thr:
                # away overpriced -> home underpriced -> buy home
                exec_p = f["pp_home"] + HALF_SPREAD
                pnl = f["out_home"] - exec_p
                trades.append((f["date"], pnl, f["game"], "buy_home", dev_away, exec_p))
        n = len(trades)
        entry = {"n_trades": n}
        if n:
            pnls = [t[1] for t in trades]
            entry["mean_pnl"] = statistics.mean(pnls)
            entry["win_rate"] = sum(1 for p in pnls if p > 0) / n
            # per-trade t
            if n > 1 and statistics.pstdev(pnls) > 0:
                sd = statistics.stdev(pnls)
                entry["t_pertrade"] = statistics.mean(pnls) / (sd / math.sqrt(n)) if sd > 0 else None
            else:
                entry["t_pertrade"] = None
            # day-clustered t
            days = {}
            for d, p, *_ in trades:
                days.setdefault(d, []).append(p)
            day_means = [statistics.mean(v) for v in days.values()]
            entry["n_days"] = len(day_means)
            if len(day_means) > 1 and statistics.stdev(day_means) > 0:
                sd = statistics.stdev(day_means)
                entry["t_dayclustered"] = statistics.mean(day_means) / (sd / math.sqrt(len(day_means)))
            else:
                entry["t_dayclustered"] = None
            entry["examples"] = [(t[2], t[3], round(t[4], 3), round(t[5], 3), round(t[1], 3)) for t in trades[:8]]
        res["thresholds"][str(thr)] = entry
    return res


def main():
    print("Collecting games...")
    # MLB: finals for backtest, plus live/upcoming for snapshot
    mlb_dates_final = ["2026-07-09", "2026-07-10", "2026-07-11", "2026-07-12", "2026-07-14", "2026-07-17"]
    mlb_dates_live = ["2026-07-17", "2026-07-18", "2026-07-19"]
    wnba_dates_final = ["2026-07-09", "2026-07-11", "2026-07-12", "2026-07-13", "2026-07-15", "2026-07-16"]
    wnba_dates_live = ["2026-07-17", "2026-07-18"]

    all_recs = []
    for d in mlb_dates_final + [x for x in mlb_dates_live if x not in mlb_dates_final]:
        recs = collect("mlb", "baseball", "mlb", d)
        all_recs += recs
        print(f"MLB {d}: {sum(1 for r in recs if r['matched'])} matched / {len(recs)} games")
    for d in wnba_dates_final + [x for x in wnba_dates_live if x not in wnba_dates_final]:
        recs = collect("wnba", "basketball", "wnba", d)
        all_recs += recs
        print(f"WNBA {d}: {sum(1 for r in recs if r['matched'])} matched / {len(recs)} games")

    matched = [r for r in all_recs if r.get("matched")]
    unmatched = [r for r in all_recs if not r.get("matched")]
    finals = [r for r in matched if r.get("final") and r.get("out_away") is not None and "pp_away" in r]
    live = [r for r in matched if not r.get("final") and "bid_away" in r]

    # dedup finals (a date can appear in both final+live lists) by (slug)
    seen = set(); uf = []
    for f in finals:
        if f["slug"] in seen:
            continue
        seen.add(f["slug"]); uf.append(f)
    finals = uf

    print(f"\nTotal matched: {len(matched)}  finals(backtestable): {len(finals)}  live: {len(live)}")

    # deviation distribution on finals (pre-game mid vs book)
    devs = [f["pp_away"] - f["pb_away"] for f in finals]
    live_devs = [l["pp_away"] - l["pb_away"] for l in live]

    bt = run_backtest(finals)

    def dist(xs):
        if not xs:
            return {}
        axs = [abs(x) for x in xs]
        return {"n": len(xs), "mean_abs": statistics.mean(axs),
                "median_abs": statistics.median(axs),
                "frac_gt_03": sum(1 for a in axs if a > 0.03) / len(axs),
                "frac_gt_05": sum(1 for a in axs if a > 0.05) / len(axs),
                "frac_gt_10": sum(1 for a in axs if a > 0.10) / len(axs),
                "max_abs": max(axs)}

    summary = {"n_matched": len(matched), "n_finals": len(finals), "n_live": len(live),
               "unmatched_reasons": {},
               "dev_finals": dist(devs), "dev_live": dist(live_devs),
               "backtest": bt,
               "live_examples": [(l["game"], round(l["pb_away"], 3), round(l["pp_away"], 3),
                                  round(l["pp_away"] - l["pb_away"], 3), l["bid_away"], l["ask_away"]) for l in live[:20]]}
    for r in unmatched:
        summary["unmatched_reasons"][r.get("reason", "?")] = summary["unmatched_reasons"].get(r.get("reason", "?"), 0) + 1

    with open("pmkt_sportsbook_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print("\n==== SUMMARY ====")
    print(json.dumps(summary, indent=2, default=str))
    return summary


if __name__ == "__main__":
    main()
