#!/usr/bin/env python3
"""pmkt_shortvol_paper.py -- FORWARD paper-trading harness for the Polymarket SHORT-VOL / longshot
risk-premium edge (node PMKT-SHORTVOL-LONGSHOT). PROPOSE-ONLY: paper only, NO orders, NO capital,
no live flag/switch/size ever touched. This is the charter gate ("tested performance must match live"):
we FORWARD-test the backtested edge under a FROZEN, conservative, pre-registered rule before any sizing.

THE EDGE (backtest: 7000 settled markets, 50 weeks): on zero-fee Polymarket, SELLING far-OTM weekly
"Will BTC/ETH be above $X on <date>?" longshots earns a short-volatility / lottery risk premium.
The robust band is entry YES price in [0.15, 0.30]: survives conservative volume-weighting
(week-clustered t=2.26), calibration solid (these settle YES ~10.5% vs ~22% priced). It is a RISK
PREMIUM, not arbitrage (Deribit cross-market was null), with REAL tail risk (worst backtest week
-0.43/contract; ~25% of weeks negative). => the harness tracks TAIL metrics, not just the mean, and
reports a fractional-Kelly (0.1), capital-bounded sizing overlay ALONGSIDE the flat 1-unit headline.

FROZEN RULE (pre-registered in PMKT_SHORTVOL.md; do NOT retune):
  Universe : Polymarket weekly binary markets "Will BTC (or ETH) be above $X on <date>?" (terminal,
             ~7-day horizon). We isolate weeklies with a horizon filter of [4, 10] days start->resolution,
             which excludes the intraday ("10AM ET") and 4h multistrike variants.
  Entry    : each run, for every OPEN such market still in the FIRST HALF of its life
             (now <= start + 0.5*(start->resolution)), if the YES mid = (best_bid+best_ask)/2 is in
             [0.15, 0.30] AND best_bid > 0 AND not already held: record a paper SELL of 1 YES unit at
             the executable price = best_bid (conservative taker; Polymarket is zero-fee). Also log the
             estimated half-spread (best_ask-best_bid)/2 at entry.
  Exit     : hold to UMA resolution. PnL/unit = sell_price - outcome  (outcome=1 if resolved YES, else 0).
             Zero fee.
  Metrics  : per-resolution-week PnL, worst-week, running max drawdown, and a fractional-Kelly(0.1)
             capital-bounded equity overlay reported alongside the flat 1-unit series.
  GATE     : PASS = week-clustered t >= 2 over >= 8 forward resolution-weeks AND mean PnL/unit > 0 AND
             worst single-week mean PnL/unit >= WORST_WEEK_TOL (stated tolerance).
             KILL = week-clustered t < 0 after >= 8 forward weeks.
             else ACCRUING.

Files (idempotent, keyed on market id): pmkt_shortvol_positions.jsonl, pmkt_shortvol_settled.jsonl
Usage: python pmkt_shortvol_paper.py snapshot | settle | report   (no subcommand = snapshot,settle,report)
"""
import urllib.request, urllib.parse, json, math, time, sys, os, re
from datetime import datetime, timezone
from collections import defaultdict
import statistics as st

GAMMA = "https://gamma-api.polymarket.com"
POS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pmkt_shortvol_positions.jsonl")
SET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pmkt_shortvol_settled.jsonl")

# ---- FROZEN parameters (pre-registered; do not retune) ----
BAND_LO, BAND_HI = 0.15, 0.30           # entry YES-price band (robust band from backtest)
MIN_HORIZON_DAYS, MAX_HORIZON_DAYS = 4.0, 10.0   # isolate the weekly (~7d) markets
FIRST_HALF = 0.5                        # only enter in the first half of a market's life
WORST_WEEK_TOL = -0.50                  # gate tolerance: worst single-week mean PnL/unit floor
MIN_WEEKS = 8                           # forward weeks required to rule on the gate
KELLY_FRAC = 0.10                       # fractional Kelly for the sizing overlay
KELLY_CAP = 0.25                        # cap: never stake >25% of bankroll in a single week (capital bound)
PRIOR_YES = 0.105                       # backtest calibration: band longshots settle YES ~10.5%
SEARCH_QUERIES = ["bitcoin above", "btc above", "ethereum above", "eth above"]


def _get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception:
            time.sleep(1 + i)
    return None


def _load(fn):
    out = []
    if os.path.exists(fn):
        with open(fn) as f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                try:
                    out.append(json.loads(l))
                except Exception:
                    pass
    return out


def _iso(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _parse_strike(q):
    m = re.search(r"\$?\s*([\d][\d,]*(?:\.\d+)?)\s*(k)?", q or "", re.I)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    if m.group(2):
        v *= 1000
    return v


def _asset(q):
    ql = (q or "").lower()
    if "bitcoin" in ql or "btc" in ql:
        return "BTC"
    if "ethereum" in ql or "eth" in ql:
        return "ETH"
    return "?"


def _iso_week(dt):
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _discover_events():
    """Return a dict {event_slug: event} of active 'above ___ on <date>' events (dedup across queries)."""
    evs = {}
    for q in SEARCH_QUERIES:
        url = f"{GAMMA}/public-search?" + urllib.parse.urlencode(
            {"q": q, "limit_per_type": 40, "events_status": "active"})
        d = _get(url)
        if not d:
            continue
        for e in d.get("events", []):
            slug = e.get("slug")
            if slug and slug not in evs and "above" in (slug or ""):
                evs[slug] = e
    return evs


def snapshot():
    now = datetime.now(timezone.utc)
    have = {p["market_id"] for p in _load(POS)}
    events = _discover_events()
    scanned, n = 0, 0
    with open(POS, "a") as f:
        for slug in sorted(events):
            # re-fetch the event fresh so best_bid/best_ask are current
            fresh = _get(f"{GAMMA}/events?slug={urllib.parse.quote(slug)}")
            ev = fresh[0] if (fresh and isinstance(fresh, list)) else events[slug]
            for m in ev.get("markets", []):
                q = m.get("question", "")
                if "above" not in q.lower():
                    continue
                start, end = _iso(m.get("startDate")), _iso(m.get("endDate"))
                if not start or not end:
                    continue
                horizon_d = (end - start).total_seconds() / 86400.0
                if not (MIN_HORIZON_DAYS <= horizon_d <= MAX_HORIZON_DAYS):
                    continue                                   # not a weekly
                if end <= now:
                    continue                                   # already terminal
                if now > start + (end - start) * FIRST_HALF:
                    continue                                   # past the first half
                mid_ = m.get("id")
                if mid_ in have:
                    continue
                bb, ba = _fnum(m.get("bestBid")), _fnum(m.get("bestAsk"))
                if bb is None or ba is None:
                    continue
                mid = (bb + ba) / 2.0
                if not (BAND_LO <= mid <= BAND_HI) or bb <= 0:
                    continue
                try:
                    yes_token = json.loads(m.get("clobTokenIds") or "[]")[0]
                except Exception:
                    yes_token = None
                rec = dict(
                    market_id=mid_, yes_token=yes_token, asset=_asset(q),
                    strike=_parse_strike(q), question=q, slug=m.get("slug"),
                    event_slug=slug, start=m.get("startDate"), resolution=m.get("endDate"),
                    horizon_days=round(horizon_d, 2), ts=now.isoformat(),
                    sell_price=bb, best_bid=bb, best_ask=ba, mid=round(mid, 4),
                    half_spread=round((ba - bb) / 2.0, 4))
                f.write(json.dumps(rec) + "\n")
                have.add(mid_)
                n += 1
            scanned += 1
    print(f"[snapshot] {len(events)} active 'above' events, {scanned} scanned, "
          f"{n} NEW paper SELLs recorded in the [{BAND_LO},{BAND_HI}] band "
          f"(total open positions now {len(have)})")
    return n


def settle():
    done = {s["market_id"] for s in _load(SET)}
    open_pos = [p for p in _load(POS) if p["market_id"] not in done]
    n = 0
    with open(SET, "a") as f:
        for p in open_pos:
            m = _get(f"{GAMMA}/markets/{p['market_id']}")
            if not m or isinstance(m, list):
                if isinstance(m, list) and m:
                    m = m[0]
                else:
                    continue
            if not m.get("closed"):
                continue
            if str(m.get("umaResolutionStatus") or "").lower() != "resolved":
                continue
            try:
                op = json.loads(m.get("outcomePrices") or "[]")
                yes_p = float(op[0])
            except Exception:
                continue
            if yes_p not in (0.0, 1.0):        # only definitive YES/NO resolutions
                continue
            outcome = 1 if yes_p == 1.0 else 0
            pnl = p["sell_price"] - outcome     # zero fee
            res_dt = _iso(p.get("resolution")) or _iso(m.get("endDate"))
            rec = dict(p, outcome=outcome, pnl=round(pnl, 4),
                       resolution_week=_iso_week(res_dt) if res_dt else "?",
                       settled_ts=datetime.now(timezone.utc).isoformat())
            f.write(json.dumps(rec) + "\n")
            n += 1
    print(f"[settle] {len(open_pos)} unresolved paper SELLs checked, {n} newly settled")
    return n


def _kelly_full(s):
    """Full-Kelly fraction of bankroll for SELLING YES at price s given frozen prior P(YES)=PRIOR_YES.
    Win s with prob (1-q) [settles NO], lose (1-s) with prob q [settles YES]. b = s/(1-s).
    f* = p_win - p_lose/b = (1-q) - q*(1-s)/s. Clamp to >=0."""
    q = PRIOR_YES
    if s <= 0 or s >= 1:
        return 0.0
    f = (1 - q) - q * (1 - s) / s
    return max(0.0, f)


def _max_drawdown(equity):
    peak, mdd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = min(mdd, v - peak)
    return mdd


def report():
    settled = _load(SET)
    n_open = len(_load(POS))
    if not settled:
        print(f"[report] PMKT-SHORTVOL forward paper gate: status=CLOCK-NOT-STARTED")
        print(f"  open paper positions={n_open}  settled=0  (no resolutions yet)")
        return
    byweek = defaultdict(list)
    for r in settled:
        byweek[r["resolution_week"]].append(r["pnl"])
    weeks = sorted(byweek)
    wmeans = [st.mean(byweek[w]) for w in weeks]
    k = len(wmeans)
    allpnl = [r["pnl"] for r in settled]
    mean = st.mean(allpnl)
    win = sum(1 for p in allpnl if p > 0) / len(allpnl)
    worst_week = min(wmeans)
    # week-clustered t: mean of per-week means / (sd/sqrt(k))
    if k >= 2 and st.stdev(wmeans) > 0:
        t = st.mean(wmeans) / (st.stdev(wmeans) / math.sqrt(k))
    else:
        t = float("nan")
    # flat 1-unit cumulative equity (sum of weekly mean PnL/unit) and its running max drawdown
    flat_eq, c = [], 0.0
    for wm in wmeans:
        c += wm
        flat_eq.append(c)
    flat_mdd = _max_drawdown(flat_eq)
    # fractional-Kelly(0.1), capital-bounded equity overlay
    E = 1.0
    keq = [E]
    for w in weeks:
        wk = byweek[w]
        # per-position stake fraction, capped, then normalized so total weekly stake <= KELLY_CAP*E
        fracs = [min(KELLY_CAP, KELLY_FRAC * _kelly_full(r["sell_price"])) for r in
                 [rr for rr in settled if rr["resolution_week"] == w]]
        recs = [rr for rr in settled if rr["resolution_week"] == w]
        tot = sum(fracs)
        scale = min(1.0, KELLY_CAP / tot) if tot > 0 else 0.0
        wpnl = 0.0
        for rr, fr in zip(recs, fracs):
            stake = fr * scale * E                      # $ at risk this position
            maxloss = max(1e-9, 1 - rr["sell_price"])   # loss per unit if YES
            contracts = stake / maxloss                 # capital-bounded contracts
            wpnl += contracts * rr["pnl"]
        E += wpnl
        keq.append(E)
    kelly_mdd = _max_drawdown(keq)

    status = ("PASS" if (k >= MIN_WEEKS and t >= 2 and mean > 0 and worst_week >= WORST_WEEK_TOL)
              else "KILL" if (k >= MIN_WEEKS and t < 0)
              else "ACCRUING")
    print(f"[report] PMKT-SHORTVOL forward paper gate: status={status}")
    print(f"  open paper positions = {n_open}   settled = {len(settled)}   "
          f"forward resolution-weeks = {k}")
    print(f"  mean PnL/unit        = {mean:+.4f}   week-clustered t = {t:.2f}   "
          f"(need t>=2 over >={MIN_WEEKS} wks)")
    print(f"  WIN rate (settle NO) = {win:.3f}   worst-week mean = {worst_week:+.4f}/unit   "
          f"(tol {WORST_WEEK_TOL:+.2f})")
    print(f"  flat 1-unit cum PnL  = {flat_eq[-1]:+.4f}/unit   running max drawdown = {flat_mdd:+.4f}/unit")
    print(f"  frac-Kelly({KELLY_FRAC}) cap<= {KELLY_CAP:.0%} bankroll: equity {1.0:.3f} -> {E:.3f}"
          f"   (x{E:.2f})   max drawdown = {kelly_mdd:+.3f}")
    print(f"  per-week means: " + "  ".join(f"{w}:{m:+.3f}" for w, m in zip(weeks, wmeans)))
    gate = (f"GATE decision -> {status}. PASS needs t>=2 over >={MIN_WEEKS} wks AND mean>0 AND "
            f"worst-week>={WORST_WEEK_TOL}; KILL if t<0 after >={MIN_WEEKS} wks. "
            f"Headline is the FLAT 1-unit series; Kelly overlay is illustrative and capital-bounded.")
    print("  " + gate)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("snapshot", "all"):
        snapshot()
    if mode in ("settle", "all"):
        settle()
    if mode in ("report", "all"):
        report()
