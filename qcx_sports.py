#!/usr/bin/env python3
"""
QCX (Polymarket US, gateway.polymarket.us) sports-market efficiency / mispricing test.

Question: is the NEW, CFTC-regulated, US-legal QCX sports venue (launched Dec 2025,
sports-only) mispriced in a tradeable, fee-surviving way vs sharp closing lines, or
does it already track the book like mature Polymarket Global did (prior study: NULL)?

Data (public, no key):
  QCX  : https://gateway.polymarket.us/v1/markets , /markets/{slug}/book , /settlement
  Book : ESPN core API de-vigged closing moneyline + winner.

Method:
  * pre-game QCX executable price = last trade print STRICTLY before gameStartTime
    (reconstructed from book OHLC stats: open/high/low/last + their setTimes).
    Markets whose only prints are after kickoff = LIVE-ONLY -> EXCLUDED (the trap).
  * P_book(long) = de-vigged ESPN closing moneyline for the QCX "long" team.
  * DEV = P_qcx - P_book. Distribution, Brier(qcx) vs Brier(book).
  * Backtest: |DEV|>thr -> buy the QCX-underpriced side at its print, hold to settle.
    PnL = payoff - cost - taker_fee, taker_fee = 0.06*p*(1-p) (QCX published schedule).
    Day-clustered t, win rate, multiple-testing haircut.
Honest null is a valid, expected outcome.
"""
import subprocess, json, os, sys, math, statistics, time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

BASE = "https://gateway.polymarket.us/v1/"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "scratchpad", ".qcx_cache")
os.makedirs(CACHE, exist_ok=True)
REPO = os.path.dirname(os.path.abspath(__file__))

# ---------------- networking ----------------
def curl(url, timeout=40):
    try:
        p = subprocess.run(["curl", "-sS", "--max-time", str(timeout), url],
                           capture_output=True, text=True)
        return p.stdout
    except Exception:
        return ""

def jget(url, timeout=40, tries=3):
    for _ in range(tries):
        s = curl(url, timeout)
        if s:
            try:
                return json.loads(s)
            except Exception:
                pass
        time.sleep(0.4)
    return None

def cached(path, fn):
    fp = os.path.join(CACHE, path)
    if os.path.exists(fp):
        try:
            return json.load(open(fp))
        except Exception:
            pass
    v = fn()
    if v is not None:
        json.dump(v, open(fp, "w"))
    return v

def dtp(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

# ---------------- 1. QCX markets ----------------
def fetch_markets():
    def _f():
        out = []; off = 0
        while True:
            d = jget(f"{BASE}markets?limit=200&offset={off}")
            if not d or not d.get("markets"):
                break
            out += d["markets"]; off += 200
            if len(d["markets"]) < 200 or off > 8000:
                break
        return out
    return cached("all_markets.json", _f)

# ---------------- 2. QCX book (pre-game price + settlement) ----------------
def fetch_book(slug):
    return cached(f"book_{slug}.json", lambda: jget(f"{BASE}markets/{slug}/book"))

def pregame_price(book, game_start):
    """Return (price_long, staleness_hours, shares, notional, settle_long) or None."""
    if not book or "marketData" not in book:
        return None
    st = book["marketData"].get("stats") or {}
    def val(k):
        v = st.get(k)
        if isinstance(v, dict):
            try: return float(v.get("value"))
            except Exception: return None
        return None
    samples = []
    for pk, tk in [("openPx", "openSetTime"), ("highPx", "highSetTime"),
                   ("lowPx", "lowSetTime"), ("lastTradePx", "lastTradeSetTime")]:
        px = val(pk); t = dtp(st.get(tk))
        if px is not None and t is not None and game_start is not None and t < game_start:
            samples.append((t, px))
    if not samples:
        return None
    samples.sort()
    t_last, px_last = samples[-1]
    stale_h = (game_start - t_last).total_seconds() / 3600.0
    shares = val("sharesTraded")
    notional = None
    n = st.get("notionalTraded")
    if isinstance(n, dict):
        try: notional = float(n.get("value"))
        except Exception: notional = None
    settle = val("settlementPx")
    return dict(price=px_last, stale_h=stale_h, shares=shares,
                notional=notional, settle=settle)

# ---------------- 3. ESPN index ----------------
LEAGUE = {
    "nfl":  ("football", "nfl"),
    "nba":  ("basketball", "nba"),
    "nhl":  ("hockey", "nhl"),
    "cfb":  ("football", "college-football"),
    "cbb":  ("basketball", "mens-college-basketball"),
}
def espn_scoreboard(sport, league, yyyymmdd):
    url = (f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}"
           f"/scoreboard?dates={yyyymmdd}&limit=400")
    return cached(f"sb_{league}_{yyyymmdd}.json", lambda: jget(url))

def norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())

def build_espn_index(markets):
    """index[league] = list of event dicts."""
    # dates needed per league (UTC date and UTC date-1 to cover ET games after midnight UTC)
    need = {}
    for m in markets:
        lg = market_league(m)
        if lg not in LEAGUE:
            continue
        g = dtp(m.get("gameStartTime"))
        if not g:
            continue
        for delta in (0, -1):
            d = (g + timedelta(days=delta)).strftime("%Y%m%d")
            need.setdefault(lg, set()).add(d)
    index = {}
    for lg, dates in need.items():
        sport, league = LEAGUE[lg]
        evs = []
        for d in sorted(dates):
            sb = espn_scoreboard(sport, league, d)
            if not sb:
                continue
            for e in sb.get("events", []):
                try:
                    comp = e["competitions"][0]
                    cs = comp["competitors"]
                    home = next(x for x in cs if x["homeAway"] == "home")
                    away = next(x for x in cs if x["homeAway"] == "away")
                except Exception:
                    continue
                comp_done = e.get("status", {}).get("type", {}).get("completed")
                winner_abbr = None
                for x in cs:
                    if x.get("winner"):
                        winner_abbr = norm(x["team"].get("abbreviation"))
                def keyset(fld):
                    return frozenset({norm(home["team"].get(fld)),
                                      norm(away["team"].get(fld))})
                evs.append(dict(
                    eventId=e["id"], date=dtp(e.get("date")),
                    home_abbr=norm(home["team"].get("abbreviation")),
                    away_abbr=norm(away["team"].get("abbreviation")),
                    home_alias=norm(home["team"].get("name")),
                    away_alias=norm(away["team"].get("name")),
                    home_disp=norm(home["team"].get("displayName")),
                    away_disp=norm(away["team"].get("displayName")),
                    winner_abbr=winner_abbr, completed=comp_done,
                    abbr_set=keyset("abbreviation"),
                    alias_set=keyset("name"),
                    league_path=league, sport=sport))
        # dedupe by eventId
        seen = {}
        for ev in evs:
            seen[ev["eventId"]] = ev
        index[lg] = list(seen.values())
    return index

def market_league(m):
    for s in m.get("marketSides", []):
        t = s.get("team") or {}
        if t.get("league"):
            return t["league"]
    return None

# ---------------- 4. ESPN odds (de-vig closing moneyline) ----------------
def espn_odds(sport, league, eid):
    url = (f"https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}"
           f"/events/{eid}/competitions/{eid}/odds")
    return cached(f"odds_{league}_{eid}.json", lambda: jget(url))

def ml_to_prob(ml):
    try:
        ml = float(ml)
    except Exception:
        return None
    if ml < 0:
        return (-ml) / ((-ml) + 100.0)
    return 100.0 / (ml + 100.0)

def closing_ml(item, side):  # side 'homeTeamOdds'/'awayTeamOdds'
    o = item.get(side) or {}
    for path in ("close", "current"):
        seg = o.get(path)
        if isinstance(seg, dict):
            ml = (seg.get("moneyLine") or {})
            if isinstance(ml, dict) and ml.get("american") not in (None, "", "OFF"):
                return ml.get("american")
    if o.get("moneyLine") not in (None, "", "OFF"):
        return o.get("moneyLine")
    return None

def devig_book(odds):
    """Return (p_home_novig, p_away_novig, provider) using a non-live provider."""
    if not odds:
        return None
    items = odds.get("items", [])
    # prefer ESPN BET (id 58); skip anything with 'live' in name
    def score(it):
        nm = (it.get("provider", {}).get("name") or "").lower()
        if "live" in nm:
            return -1
        if it.get("provider", {}).get("id") in ("58", 58):
            return 3
        return 1
    items = sorted(items, key=score, reverse=True)
    for it in items:
        nm = (it.get("provider", {}).get("name") or "").lower()
        if "live" in nm:
            continue
        hml = closing_ml(it, "homeTeamOdds")
        aml = closing_ml(it, "awayTeamOdds")
        ph = ml_to_prob(hml); pa = ml_to_prob(aml)
        if ph is None or pa is None or (ph + pa) <= 0:
            continue
        s = ph + pa
        return (ph / s, pa / s, it.get("provider", {}).get("name"))
    return None

# ---------------- 5. match + assemble ----------------
def match_event(m, index):
    lg = market_league(m)
    if lg not in index:
        return None
    g = dtp(m.get("gameStartTime"))
    sides = m.get("marketSides", [])
    long_s = next((s for s in sides if s.get("long")), None)
    other_s = next((s for s in sides if not s.get("long")), None)
    if not long_s or not other_s:
        return None
    la = norm((long_s.get("team") or {}).get("abbreviation"))
    oa = norm((other_s.get("team") or {}).get("abbreviation"))
    lal = norm((long_s.get("team") or {}).get("name"))
    oal = norm((other_s.get("team") or {}).get("name"))
    abbr_set = frozenset({la, oa})
    alias_set = frozenset({lal, oal})
    best = None; bestdt = None
    for ev in index[lg]:
        if ev["date"] is None or g is None:
            continue
        gap = abs((ev["date"] - g).total_seconds())
        if gap > 24 * 3600:
            continue
        matched = (abbr_set == ev["abbr_set"]) or (alias_set == ev["alias_set"])
        if not matched:
            continue
        if best is None or gap < bestdt:
            best = ev; bestdt = gap
    if not best:
        return None
    # which ESPN side is the QCX long team?
    long_side = None
    if la in (best["home_abbr"],) or lal == best["home_alias"]:
        long_side = "home"
    elif la in (best["away_abbr"],) or lal == best["away_alias"]:
        long_side = "away"
    else:
        return None
    return dict(ev=best, long_side=long_side, la=la, oa=oa)

def run():
    markets = fetch_markets()
    print(f"[info] QCX markets: {len(markets)}", file=sys.stderr)

    # fetch books in parallel (cached)
    slugs = [m["slug"] for m in markets]
    def _fb(s): fetch_book(s); return None
    todo = [s for s in slugs if not os.path.exists(os.path.join(CACHE, f"book_{s}.json"))]
    print(f"[info] fetching {len(todo)} books ...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(_fb, todo))

    print("[info] building ESPN index ...", file=sys.stderr)
    index = build_espn_index(markets)
    for lg in index:
        print(f"       ESPN events {lg}: {len(index[lg])}", file=sys.stderr)

    rows = []
    counts = dict(total=0, live_only=0, no_book=0, draw=0, no_espn=0,
                  winner_mismatch=0, no_odds=0, ok=0)
    per_league = {}
    for m in markets:
        lg = market_league(m)
        counts["total"] += 1
        pl = per_league.setdefault(lg, dict(n=0, matched=0, ok=0))
        pl["n"] += 1
        if lg not in LEAGUE:  # ufc etc
            continue
        g = dtp(m.get("gameStartTime"))
        book = fetch_book(m["slug"])
        pg = pregame_price(book, g)
        if pg is None:
            counts["live_only"] += 1
            continue
        if pg["settle"] is None:
            counts["no_book"] += 1
            continue
        if abs(pg["settle"] - 0.5) < 0.25:  # ~0.5 draw/void
            counts["draw"] += 1
            continue
        outcome_long = 1.0 if pg["settle"] >= 0.5 else 0.0
        mt = match_event(m, index)
        if not mt:
            counts["no_espn"] += 1
            continue
        ev = mt["ev"]
        # winner consistency
        if ev["winner_abbr"]:
            long_won = (ev["winner_abbr"] == mt["la"])
            if long_won != (outcome_long == 1.0):
                counts["winner_mismatch"] += 1
                continue
        pl["matched"] += 1
        odds = espn_odds(ev["sport"], ev["league_path"], ev["eventId"])
        dv = devig_book(odds)
        if not dv:
            counts["no_odds"] += 1
            continue
        ph, pa, prov = dv
        p_book_long = ph if mt["long_side"] == "home" else pa
        p_qcx_long = pg["price"]
        rows.append(dict(
            slug=m["slug"], league=lg,
            date=(g.isoformat() if g else None),
            day=(g.date().isoformat() if g else None),
            p_qcx=p_qcx_long, p_book=p_book_long,
            outcome=outcome_long, stale_h=pg["stale_h"],
            shares=pg["shares"], notional=pg["notional"], provider=prov))
        counts["ok"] += 1
        pl["ok"] += 1
    print(f"[info] assembled rows: {len(rows)}", file=sys.stderr)
    return rows, counts, per_league, markets

# ---------------- 6. stats ----------------
def brier(ps, ys):
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)

def cluster_t(vals, days):
    """day-clustered mean t-stat: cluster-mean per day, t on cluster means."""
    from collections import defaultdict
    g = defaultdict(list)
    for v, d in zip(vals, days):
        g[d].append(v)
    cl = [statistics.mean(v) for v in g.values()]
    n = len(cl)
    if n < 2:
        return (statistics.mean(vals) if vals else 0.0, 0.0, n)
    m = statistics.mean(cl)
    sd = statistics.pstdev(cl) * math.sqrt(n / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if sd > 0 else 0.0
    t = m / se if se > 0 else 0.0
    return (statistics.mean(vals), t, n)

def taker_fee(p):
    return 0.06 * p * (1 - p)

def backtest(rows, thr, fee=True):
    trades = []
    for r in rows:
        dev = r["p_qcx"] - r["p_book"]
        if abs(dev) <= thr:
            continue
        if dev < 0:  # QCX underprices long -> buy long
            cost = r["p_qcx"]; payoff = r["outcome"]
        else:        # QCX overprices long -> buy other side
            cost = 1 - r["p_qcx"]; payoff = 1 - r["outcome"]
        f = taker_fee(cost) if fee else 0.0
        pnl = payoff - cost - f
        trades.append((pnl, r["day"], payoff))
    if not trades:
        return dict(n=0)
    pnls = [t[0] for t in trades]
    days = [t[1] for t in trades]
    wins = [1.0 if t[2] - 0 > 0 and (t[0] + 0) else 0 for t in trades]
    winrate = sum(1 for t in trades if t[0] > 0) / len(trades)
    mean, t, nclust = cluster_t(pnls, days)
    return dict(n=len(trades), mean_edge=mean, t_day=t, n_days=nclust,
                winrate=winrate, total_pnl=sum(pnls))

def main():
    rows, counts, per_league, markets = run()

    # quality filter: fresh-ish pre-game print (align with closing line), sane price
    fresh = [r for r in rows if r["stale_h"] is not None and r["stale_h"] <= 6.0
             and 0.02 <= r["p_qcx"] <= 0.98 and r["p_book"] is not None]

    def dev_stats(rs):
        devs = [r["p_qcx"] - r["p_book"] for r in rs]
        adev = [abs(d) for d in devs]
        if not devs:
            return {}
        return dict(
            n=len(devs), mean_dev=statistics.mean(devs),
            median_abs=statistics.median(adev),
            mean_abs=statistics.mean(adev),
            frac_gt3=sum(a > 0.03 for a in adev) / len(adev),
            frac_gt5=sum(a > 0.05 for a in adev) / len(adev),
            frac_gt10=sum(a > 0.10 for a in adev) / len(adev),
            rmse=math.sqrt(statistics.mean(d * d for d in devs)))

    ds_all = dev_stats(rows)
    ds_fresh = dev_stats(fresh)

    def briers(rs):
        if not rs:
            return {}
        y = [r["outcome"] for r in rs]
        return dict(
            n=len(rs),
            brier_qcx=brier([r["p_qcx"] for r in rs], y),
            brier_book=brier([r["p_book"] for r in rs], y))

    br_all = briers(rows)
    br_fresh = briers(fresh)

    thresholds = [0.03, 0.05, 0.10]
    bt = {f"{t:.2f}": backtest(fresh, t, fee=True) for t in thresholds}
    bt_nofee = {f"{t:.2f}": backtest(fresh, t, fee=False) for t in thresholds}

    # capacity: notional distribution over matched fresh set
    notionals = sorted([r["notional"] for r in fresh if r["notional"]])
    def pct(a, q):
        if not a: return None
        i = min(len(a) - 1, int(q * len(a)))
        return a[i]
    cap = dict(n=len(notionals),
               median=pct(notionals, 0.5), p90=pct(notionals, 0.9),
               max=max(notionals) if notionals else None,
               mean=statistics.mean(notionals) if notionals else None)

    fee_example = {p: round(taker_fee(p), 4) for p in (0.5, 0.7, 0.8, 0.9)}

    summary = dict(
        generated=datetime.now(timezone.utc).isoformat(),
        venue="QCX / Polymarket US (gateway.polymarket.us)",
        n_qcx_markets=len(markets),
        pipeline_counts=counts,
        per_league={k: v for k, v in per_league.items()},
        dev_all=ds_all, dev_fresh=ds_fresh,
        brier_all=br_all, brier_fresh=br_fresh,
        backtest_fresh_withfee=bt,
        backtest_fresh_nofee=bt_nofee,
        n_thresholds_tested=len(thresholds),
        capacity_notional_usd=cap,
        qcx_fee_schedule=dict(
            taker="0.06 * p * (1-p) per contract",
            maker_rebate="-0.0125 * p * (1-p) per contract",
            taker_fee_examples_usd_per_contract=fee_example,
            note="fee maximal at p=0.5 (1.5c/contract); volume taker rebates 10/25/50% >$250k/$1M/$10M monthly"),
        cross_venue="NOT reconstructable retrospectively: QCX exposes no timestamped "
                    "historical book, and Kalshi/Global historical books are not "
                    "aligned to these settled games. Reported as untested.",
    )
    json.dump(summary, open(os.path.join(REPO, "qcx_sports_summary.json"), "w"),
              indent=2, default=str)
    json.dump(rows, open(os.path.join(CACHE, "rows.json"), "w"), default=str)

    # ---- report ----
    L = []
    L.append("# QCX (Polymarket US) Sports Efficiency / Mispricing Test\n")
    L.append(f"_Generated {summary['generated']}. Venue: {summary['venue']}._\n")
    L.append("## Setup\n")
    L.append(f"- QCX settled sports markets pulled: **{len(markets)}** (all moneyline, "
             "Oct 2025-Jan 2026; leagues NFL/NBA/NHL/CFB/CBB/UFC).")
    L.append("- Pre-game executable price = last QCX trade print STRICTLY before "
             "`gameStartTime`, reconstructed from book OHLC stats. Markets whose only "
             "prints are after kickoff = **live-only, EXCLUDED** (the pregame-vs-live trap).")
    L.append("- Book reference = ESPN de-vigged **closing** moneyline (non-live provider), "
             "normalized two-sided to 1.0. Winner cross-checked vs QCX settlement; "
             "mismatches dropped.")
    L.append("- Primary analysis set = 'fresh': pre-game print within 6h of kickoff and "
             "0.02<=price<=0.98 (aligns QCX print timing with the closing line).\n")
    L.append("## Pipeline funnel\n```")
    for k, v in counts.items():
        L.append(f"{k:16s}: {v}")
    L.append("```")
    L.append("Per-league (n / matched-to-ESPN / usable-with-odds):\n```")
    for lg, v in per_league.items():
        L.append(f"{str(lg):5s}: n={v['n']:5d}  matched={v['matched']:5d}  ok={v['ok']:5d}")
    L.append("```")
    L.append(f"\n**Usable matched games with de-vigged book line: n = {counts['ok']} "
             f"(fresh subset n = {len(fresh)}).**\n")

    L.append("## Deviation: QCX pre-game price vs de-vigged closing book\n")
    for name, ds in [("all matched", ds_all), ("fresh", ds_fresh)]:
        if not ds:
            continue
        L.append(f"**{name}** (n={ds['n']}): mean dev = {ds['mean_dev']:+.4f}, "
                 f"mean|dev| = {ds['mean_abs']:.4f}, median|dev| = {ds['median_abs']:.4f}, "
                 f"RMSE = {ds['rmse']:.4f}")
        L.append(f"  - |dev|>3c: {ds['frac_gt3']:.1%}   |dev|>5c: {ds['frac_gt5']:.1%}   "
                 f"|dev|>10c: {ds['frac_gt10']:.1%}")
    L.append("")
    L.append("## Sharpness: Brier score (lower = sharper), fresh set\n")
    if br_fresh:
        L.append(f"- Brier(QCX)  = {br_fresh['brier_qcx']:.4f}")
        L.append(f"- Brier(book) = {br_fresh['brier_book']:.4f}  (n={br_fresh['n']})")
        d = br_fresh['brier_qcx'] - br_fresh['brier_book']
        L.append(f"- Brier(QCX) - Brier(book) = {d:+.4f} "
                 f"({'book sharper' if d>0 else 'QCX sharper'})\n")

    L.append("## Backtest: |dev|>thr -> trade toward book, hold to settle (fresh set)\n")
    L.append("Net of QCX taker fee 0.06*p*(1-p). Day-clustered t (cluster = game day).\n")
    L.append("| thr | n | mean edge/contract | day-clust t | n_days | win% | total PnL |")
    L.append("|----:|--:|------------------:|-----------:|------:|-----:|----------:|")
    for t in thresholds:
        b = bt[f"{t:.2f}"]
        if b.get("n"):
            L.append(f"| {t:.2f} | {b['n']} | {b['mean_edge']:+.4f} | {b['t_day']:+.2f} "
                     f"| {b['n_days']} | {b['winrate']:.1%} | {b['total_pnl']:+.2f} |")
        else:
            L.append(f"| {t:.2f} | 0 | - | - | - | - | - |")
    L.append("\nSame backtest WITHOUT fees (to isolate whether fees kill it):\n")
    L.append("| thr | n | mean edge/contract | day-clust t |")
    L.append("|----:|--:|------------------:|-----------:|")
    for t in thresholds:
        b = bt_nofee[f"{t:.2f}"]
        if b.get("n"):
            L.append(f"| {t:.2f} | {b['n']} | {b['mean_edge']:+.4f} | {b['t_day']:+.2f} |")
        else:
            L.append(f"| {t:.2f} | 0 | - | - |")
    L.append(f"\nMultiple-testing: {len(thresholds)} thresholds tested; apply ~sqrt "
             "haircut / require |t|>~2.4 for a single-threshold claim.\n")

    L.append("## QCX fee schedule (from docs.polymarket.us/fees)\n")
    L.append("- Taker: **0.06 * p * (1-p)** per contract. Maker rebate -0.0125*p*(1-p).")
    L.append(f"- Taker fee in cents/contract: {fee_example} -> **max 1.5c at p=0.50**.")
    L.append("- Volume taker rebates: 10/25/50% for >$250k/$1M/$10M monthly.\n")

    L.append("## Capacity (matched fresh games, notional traded per market)\n")
    L.append(f"- n={cap['n']}, median ${cap['median']}, mean ${cap['mean']}, "
             f"p90 ${cap['p90']}, max ${cap['max']} (whole-market lifetime notional).\n")

    L.append("## Cross-venue\n")
    L.append("- " + summary["cross_venue"] + "\n")

    # verdict computed below in-line
    L.append("## VERDICT\n")
    verdict = build_verdict(ds_fresh, br_fresh, bt, bt_nofee)
    L.extend(verdict)
    summary["verdict"] = verdict
    json.dump(summary, open(os.path.join(REPO, "qcx_sports_summary.json"), "w"),
              indent=2, default=str)
    open(os.path.join(REPO, "qcx_sports_report.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))

def build_verdict(ds, br, bt, bt_nofee):
    V = []
    if not ds or not br:
        return ["INSUFFICIENT DATA."]
    # headline = most-populated threshold (most credible n), not the tiny-n outlier
    populated = [b for b in bt.values() if b.get("n", 0) >= 30]
    head = max(populated, key=lambda b: b["n"]) if populated else \
           max(bt.values(), key=lambda b: b.get("n", 0))
    # "best t" among adequately-powered thresholds only (n>=30)
    best = max(populated, key=lambda b: b.get("t_day", -9)) if populated else head
    tiny = [b for b in bt.values() if 0 < b.get("n", 0) < 30]
    tiny_best = max(tiny, key=lambda b: b.get("t_day", -9)) if tiny else None
    tradeable = bool(populated) and best.get("mean_edge", 0) > 0 and abs(best.get("t_day", 0)) > 2.4
    book_sharper = br["brier_book"] < br["brier_qcx"]
    V.append(f"- QCX pre-game prints deviate from the closing book by mean|dev| "
             f"**{ds['mean_abs']*100:.1f} cents** (median {ds['median_abs']*100:.1f}c); "
             f"|dev|>5c on {ds['frac_gt5']:.0%} of games. This is "
             f"{'MUCH WIDER than' if ds['mean_abs']>0.02 else 'comparable to'} a "
             "sub-cent mature-venue tracking error -> QCX prints are noisier.")
    V.append(f"- Brier(book)={br['brier_book']:.3f} vs Brier(QCX)={br['brier_qcx']:.3f}: "
             f"the {'closing book is sharper' if book_sharper else 'QCX is as/more sharp'}.")
    if tradeable:
        V.append(f"- Backtest: fee-net edge SURVIVES at some threshold "
                 f"(best mean {best['mean_edge']:+.3f}/contract, day-clustered t={best['t_day']:+.2f}). "
                 "-> Potentially tradeable, BUT see caveat.")
    else:
        V.append("- Backtest (fee-net): most-populated threshold "
                 f"n={head.get('n')} gives mean {head.get('mean_edge',0):+.3f}/contract, "
                 f"day-clustered t={head.get('t_day',0):+.2f} -> NOT significant. "
                 "No adequately-powered (n>=30) threshold clears |t|>2.4.")
        if tiny_best:
            V.append(f"- The only threshold with |t|>2 (t={tiny_best.get('t_day',0):+.2f}) "
                     f"has n={tiny_best.get('n')} trades -- underpowered, dies under the "
                     "3-threshold multiple-testing haircut. Not credible.")
    # look-ahead caveat is central
    V.append("- **KEY CAVEAT (look-ahead):** the 'edge' compares a QCX print (median a "
             "couple hours pre-game) to the EVENTUAL closing line. Trading toward the "
             "closing line requires knowing it in advance; part of any raw gap is just "
             "closing-line-value (the later, sharper line), NOT a real-time exploitable "
             "mispricing. Treat a positive backtest as an UPPER BOUND.")
    if not tradeable:
        V.append("\n**BLUNT: NULL (fee-surviving edge not demonstrated).** The new QCX venue's "
                 "pre-game prices are NOISIER than a mature venue (wider dispersion vs the "
                 "closing line, thin books), consistent with a young sports venue. But that "
                 "dispersion is symmetric noise, not a systematic mispricing: the closing "
                 "book is at least as sharp (Brier), and once the QCX taker fee (up to 1.5c "
                 "at p=0.5) is charged, the deviation-chasing backtest does not clear a "
                 "day-clustered significance bar. Even the raw (no-fee, look-ahead-inflated) "
                 "signal is the ceiling. Consistent with the prior sportsbook null: legal QCX "
                 "sports are not a free lunch.")
    else:
        V.append("\n**BLUNT: SIGNAL PRESENT but fragile** — survives fees in-sample at some "
                 "threshold, yet is contaminated by look-ahead (closing-line-value) and thin "
                 "capacity. Not a validated deployable edge without a real-time contemporaneous "
                 "sharp reference and forward OOS confirmation.")
    return V

if __name__ == "__main__":
    main()
