#!/usr/bin/env python3
"""wx_earlylock_forward.py -- READ-ONLY / PAPER forward PRICE-LOGGER for the "early-lock" refinement.

WHY: wx_earlylock_study.py PROVED the PREDICTABILITY half of early-lock -- at threshold 0.95 a per-station
diurnal climatology calls daily-HIGH strike clearance a median ~60 min BEFORE the mechanical lock at ~96.88%
pooled win. But predictability alone does NOT decide deployment. The deployed mechanical-lock baseline buys the
same rung at ~98c (~99.6% win, EV ~+1.1c/ct). An early rung at 96.88% win only BEATS that baseline if it can be
bought <= ~95.3c (break-even); at <=92c EV roughly quadruples. Whether the LIVE market actually offers those
early rungs that cheap -- or has already priced the same forecast to >=96c ("dead") -- is UNKNOWN from backtest.
This harness MEASURES it, paper-only, by logging the real yes-ask at each early-lock signal moment:

  snapshot : one live pass. For each active daily-HIGH city today (HIGHS ONLY -- the study is the HIGH case),
             pull the current observed running-max the exact way kwx_runner does (feed_for_station), and for each
             floor-only "X>strike" rung compute the early-lock signal from the PERSISTED fixed climatology:
             predicted_final = running_max + E[remaining_rise | current LST bin]; P_clear = P(final > strike)
             under Normal(predicted_final, resid_std). If P_clear >= 0.95 AND the mechanical lock has NOT yet
             fired (running_max has not cleared strike+margin), log ONE paper row capturing the live yes_ask.
             Idempotent per (ticker, date). No orders, no look-ahead: settlement is scored later from IEM ASOS.
  settle   : for logged rows whose LST day has passed, fetch the realized official ASOS daily max from IEM,
             decide cleared vs not, and compute paper pnl/contract at the LOGGED yes_ask net of the Kalshi fee.
  report   : from settled rows print n / win% / mean captured entry price (THE key number: did early rungs sit
             below the ~95.3c break-even?) / EV per contract vs the +1.1c baseline / day-clustered t, the
             captured-yes_ask distribution (median/p25/p75 -- do asks cluster <=92c=build or >=96c=dead), and a
             verdict: "EARLY-LOCK BEATS BASELINE" only if EV/ct > +1.1c with n>=20, else "insufficient/priced-in".

PROPOSE-ONLY / PAPER: never places orders, never reads credentials, never sets KWX_LIVE, never touches the live
runner's trade path. Reads public Kalshi + IEM + the cached climatology only. stdlib + numpy/scipy only. TLS via
the session CA bundle exactly as the sibling modules do. Mirrors wx_forecast_forward.py's structure/idempotency.

Usage:
    python wx_earlylock_forward.py snapshot   # one live pass -> log paper rows to wx_earlylock_paper.jsonl
    python wx_earlylock_forward.py settle     # score rows whose LST day has passed -> wx_earlylock_settled.jsonl
    python wx_earlylock_forward.py report     # captured-price distribution + EV vs baseline + verdict
"""
import os, ssl, sys, json, math, io, csv, datetime as dt, urllib.request
from collections import defaultdict

from scipy.stats import norm

import kwx_runner as R
import wx_forecast_model as M
import wx_earlylock_study as S

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
PAPER = os.path.join(HERE, "wx_earlylock_paper.jsonl")
SETTLED = os.path.join(HERE, "wx_earlylock_settled.jsonl")
CLIMO = S.CLIMO_PATH

# --- early-lock knobs (from the Phase-1 study + earlylock_ev.py break-even) ---
THR = 0.95                 # log a paper row when P_clear >= this (the study's thr-0.95 tier: 96.88% pooled win)
BASELINE_EV_C = 1.1        # deployed mechanical-lock EV in cents/contract (buy ~98c, ~99.6% win) -- the yardstick
BREAKEVEN_C = 95.3         # at 96.88% win, entry <= this beats the baseline EV (earlylock_ev.py); <=92c ~4x's it
BIN = S.BIN                # 15-min local-time climatology bin width (must match the persisted climatology)


def _get_text(url, to=30):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "text/plain"}), timeout=to, context=_CTX).read().decode()


def _kalshi_fee(price_dollars):
    """Standard Kalshi quadratic fee (multiplier 1), rounded up to the cent per contract -- identical to
    wx_forecast_forward._kalshi_fee so paper pnl matches the other sleeves' accounting."""
    return math.ceil(0.07 * price_dollars * (1 - price_dollars) * 100) / 100.0


def _load_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def load_climatology(verbose=True):
    """Load the persisted FIXED climatology (fast, no refetch). If missing, build it once from the cache via the
    study (build_fixed_climatology reads ./_earlylock_cache and writes _earlylock_climatology.json)."""
    if not os.path.exists(CLIMO):
        if verbose:
            print(f"climatology {CLIMO} missing -> building once from cache (this may fetch if cache is cold)...")
        S.build_fixed_climatology(verbose=verbose)
    with open(CLIMO) as f:
        return json.load(f)


# ---------------- snapshot ----------------
def snapshot(verbose=True):
    """One live pass. HIGHS ONLY. For each active daily-HIGH city, read the current running-max (the runner's
    feed path) and, per floor-only 'X>strike' rung, compute P_clear from the persisted climatology. Log ONE
    paper row per rung when P_clear >= THR AND the mechanical lock has NOT yet fired. Idempotent on (ticker, date)."""
    climo = load_climatology(verbose=verbose)
    stns = climo.get("stations", {})
    seen = {(r["ticker"], r["date"]) for r in _load_jsonl(PAPER)}
    now_utc = dt.datetime.now(tz=dt.timezone.utc)
    n_events = 0        # daily-HIGH events with a live ladder + a running-max
    n_rows = 0
    examples = []
    fout = open(PAPER, "a")
    for series, ev, station, offset, lst_date, kind in R.active_market_days():
        if kind != "max":          # HIGHS ONLY -- the early-lock study is the daily-HIGH case (temp rises to peak)
            continue
        binmap = stns.get(station)
        if not binmap:             # no persisted climatology for this station -> can't signal; skip
            continue
        rungs = R.event_rungs(ev)
        if not rungs:
            continue
        # current observed running-max, obtained the SAME way the live runner does (feed_for_station + sustain filter)
        try:
            feed = R.feed_for_station(station).running_extreme(station, lst_date, offset, kind)
        except Exception as e:
            if verbose:
                print(f"  [feed skip] {station}: {type(e).__name__}")
            continue
        if not feed:
            continue
        running_max = R.sustained_extreme(feed.get("obs") or [], kind)
        if running_max is None:
            running_max = feed.get("extreme_f")
        if running_max is None:
            continue
        # current LST minute-of-day -> climatology bin -> (E[remaining_rise], resid_std)
        now_local = now_utc + dt.timedelta(hours=offset)
        lst_min = now_local.hour * 60 + now_local.minute
        est = binmap.get(str(lst_min // BIN))
        if not est:                # no climatology for this bin (e.g. deep night) -> skip
            continue
        mean_rise, resid_std = float(est[0]), float(est[1])
        predicted_final = running_max + mean_rise
        st_margin = R.STATION_MARGIN.get(station, R.MARGIN_F)   # same per-station margin the runner locks on
        n_events += 1
        for r in rungs:
            floor, cap = r.get("floor"), r.get("cap")
            # the early-lock signal is the daily-HIGH YES side: a floor-only "X > floor" rung (the deployed
            # mechanical-lock buys YES on exactly these). Skip capped/range rungs (not the study's swept case).
            if cap is not None or floor is None:
                continue
            yes_ask_c = r.get("yes_ask_c")
            if not yes_ask_c:      # no live yes offer -> nothing to price-capture; skip
                continue
            # mechanical-lock GATE: only log a GENUINELY-EARLY signal -- one fired BEFORE running_max cleared
            # strike+margin (once it clears, the deployed bot already buys it; there is no earlier/cheaper entry).
            if running_max > floor + st_margin:
                continue
            p_clear = float(norm.sf(floor, predicted_final, resid_std))   # P(final daily max > strike)
            if p_clear < THR:
                continue
            k = (r["ticker"], lst_date)
            if k in seen:          # idempotent per (ticker, date): never double-log a rung the same day
                continue
            seen.add(k)
            row = {
                "ts": now_utc.isoformat(), "date": lst_date, "city": series, "station": station,
                "ticker": r["ticker"], "strike": floor,
                "running_max": round(float(running_max), 2), "predicted_final": round(predicted_final, 2),
                "mean_rise": round(mean_rise, 3), "resid_std": round(resid_std, 3),
                "p_clear": round(p_clear, 4), "yes_ask_c": yes_ask_c,
                "deg_to_strike": round(floor - float(running_max), 2),   # >0 = temp still below strike (predictive)
                "lst_min": lst_min, "margin": st_margin, "thr": THR,
            }
            fout.write(json.dumps(row) + "\n")
            n_rows += 1
            if len(examples) < 10:
                examples.append(row)
    fout.close()
    if verbose:
        print(f"snapshot: {n_events} daily-HIGH events with ladder+running-max, {n_rows} new early-lock paper "
              f"rows (P_clear>={THR}, pre-mechanical-lock) -> {PAPER}")
        for r in examples:
            print(f"  {r['city']:<11} {r['station']:<4} strike={r['strike']:<3} run_max={r['running_max']:.1f} "
                  f"pred={r['predicted_final']:.1f} p_clear={r['p_clear']:.3f} yes_ask={r['yes_ask_c']}c "
                  f"(temp {r['deg_to_strike']:+.1f}F to strike)")
    return n_rows


# ---------------- settle ----------------
def _iem_daily_max(station, date_iso):
    """Realized official ASOS daily max_temp_f for a station on a local date, or None. Copies
    wx_forecast_forward._iem_daily (IEM daily.py, comma format), HIGH case only."""
    net = M.STATIONS[station][3]
    stid = M.iem_station(station)
    y, m, d = date_iso.split("-")
    q = (f"?network={net}&stations={stid}&year1={y}&month1={int(m)}&day1={int(d)}"
         f"&year2={y}&month2={int(m)}&day2={int(d)}&var=max_temp_f,min_temp_f&format=comma")
    try:
        txt = _get_text(IEM + q)
    except Exception:
        return None
    for row in csv.DictReader(io.StringIO(txt)):
        if row.get("day") == date_iso:
            try:
                return float(row.get("max_temp_f"))
            except (TypeError, ValueError):
                return None
    return None


def settle(verbose=True):
    rows = _load_jsonl(PAPER)
    already = {(r["ticker"], r["date"]) for r in _load_jsonl(SETTLED)}
    truth = {}   # (station, date) -> realized daily max; cache IEM calls
    today_utc = dt.datetime.now(tz=dt.timezone.utc).date()
    n_new = 0
    fout = open(SETTLED, "a")
    for r in rows:
        key = (r["ticker"], r["date"])
        if key in already:
            continue
        # only settle once the LST day is fully over (settlement date strictly before today's UTC date is a
        # safe no-look-ahead bound; ASOS daily is finalized after local midnight, same rule as the sibling harness).
        try:
            d = dt.date.fromisoformat(r["date"])
        except Exception:
            continue
        if d >= today_utc:
            continue
        tk = (r["station"], r["date"])
        if tk not in truth:
            truth[tk] = _iem_daily_max(r["station"], r["date"])
        realized = truth[tk]
        if realized is None:
            continue   # not yet available -> retry next run
        cleared = realized > r["strike"]         # YES ("X > strike") wins iff realized daily max exceeded strike
        price = r["yes_ask_c"] / 100.0           # paper entry at the LOGGED live ask (the whole point of the test)
        fee = _kalshi_fee(price)
        pnl = (1.0 - price - fee) if cleared else (-price - fee)
        rec = {**r, "realized_max": realized, "cleared": cleared, "won": cleared,
               "fee": fee, "pnl": round(pnl, 4)}
        fout.write(json.dumps(rec) + "\n")
        already.add(key)
        n_new += 1
    fout.close()
    if verbose:
        print(f"settled {n_new} new early-lock paper rows -> {SETTLED}")
    return n_new


# ---------------- report ----------------
def _pctile(vals, q):
    if not vals:
        return float("nan")
    s = sorted(vals)
    if len(s) == 1:
        return float(s[0])
    pos = q / 100.0 * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return float(s[lo] + (s[hi] - s[lo]) * (pos - lo))


def report():
    rows = _load_jsonl(SETTLED)
    if not rows:
        print("=== WX EARLY-LOCK FORWARD PAPER (does the market actually offer early rungs cheaply?) ===")
        print("no settled rows yet. Run `snapshot` during US afternoon rising-temp windows to log early-lock")
        print("paper rows, then `settle` after each day ends.")
        print(f"(signal threshold P_clear >= {THR}; baseline EV = {BASELINE_EV_C:+.1f}c/ct; "
              f"break-even entry <= {BREAKEVEN_C:.1f}c)")
        return
    import statistics as stt
    pnls = [r["pnl"] for r in rows]
    asks = [r["yes_ask_c"] for r in rows]
    n = len(rows)
    wins = sum(1 for r in rows if r["won"])
    ev_c = stt.mean(pnls) * 100.0                       # EV per contract in cents (net of fee)
    mean_ask = stt.mean(asks)

    # day-clustered t on per-contract pnl (guards against one lucky day inflating significance)
    byday = defaultdict(list)
    for r in rows:
        byday[r["date"]].append(r["pnl"])
    dm = [stt.mean(v) for v in byday.values()]
    t = (stt.mean(dm) / (stt.stdev(dm) / math.sqrt(len(dm)))) if len(dm) > 1 and stt.stdev(dm) > 0 else float("nan")

    print("=== WX EARLY-LOCK FORWARD PAPER (does the market actually offer early rungs cheaply?) ===")
    print(f"  n paper rungs     : {n}   ({len(byday)} days)")
    print(f"  win rate          : {wins/n:.1%}   (study claim @ thr-{THR}: ~96.88% pooled)")
    print(f"  mean entry ask    : {mean_ask:.1f}c   (KEY: break-even to beat baseline is <= {BREAKEVEN_C:.1f}c)")
    print(f"  EV / contract     : {ev_c:+.2f}c   (net of Kalshi fee)   vs baseline {BASELINE_EV_C:+.1f}c")
    print(f"  day-clustered t   : {t:.2f}")
    print(f"  worst / best pnl  : {min(pnls)*100:+.1f}c / {max(pnls)*100:+.1f}c")

    # CAPTURED-PRICE DISTRIBUTION -- the deciding picture: do asks cluster <=92c (build it) or >=96c (dead)?
    med, p25, p75 = _pctile(asks, 50), _pctile(asks, 25), _pctile(asks, 75)
    print("\n  CAPTURED yes_ask DISTRIBUTION (the deciding picture):")
    print(f"    p25={p25:.0f}c   median={med:.0f}c   p75={p75:.0f}c   min={min(asks)}c   max={max(asks)}c")
    n_cheap = sum(1 for a in asks if a <= 92)
    n_be = sum(1 for a in asks if a <= BREAKEVEN_C)
    n_dead = sum(1 for a in asks if a >= 96)
    print(f"    <=92c (build it): {n_cheap}/{n} ({n_cheap/n:.0%})   "
          f"<=break-even {BREAKEVEN_C:.0f}c: {n_be}/{n} ({n_be/n:.0%})   "
          f">=96c (priced-in): {n_dead}/{n} ({n_dead/n:.0%})")

    # ask decile -> realized win + pnl (sanity: are the cheap ones still winning?)
    print("\n  by entry-ask bucket (does a cheaper ask still win?):")
    print(f"    {'ask bucket':<12} {'n':>4} {'win%':>7} {'EV/ct':>8}")
    abuck = defaultdict(list)
    for r in rows:
        a = r["yes_ask_c"]
        b = "<=90c" if a <= 90 else "91-95c" if a <= 95 else "96-98c" if a <= 98 else "99c+"
        abuck[b].append(r)
    for b in ("<=90c", "91-95c", "96-98c", "99c+"):
        s = abuck.get(b)
        if s:
            print(f"    {b:<12} {len(s):>4} {sum(1 for r in s if r['won'])/len(s):>6.1%} "
                  f"{stt.mean([r['pnl'] for r in s])*100:>+7.2f}c")

    # VERDICT: only a beat if EV clears the baseline AND we have enough evidence (n>=20).
    if ev_c > BASELINE_EV_C and n >= 20:
        verdict = f"EARLY-LOCK BEATS BASELINE (EV {ev_c:+.2f}c > {BASELINE_EV_C:+.1f}c, n={n})"
    elif n < 20:
        verdict = f"insufficient / priced-in -- need n>=20 (have {n}); keep snapshotting"
    else:
        verdict = (f"insufficient / priced-in -- EV {ev_c:+.2f}c does NOT beat baseline {BASELINE_EV_C:+.1f}c "
                   f"(market prices the early signal; mean ask {mean_ask:.1f}c vs break-even {BREAKEVEN_C:.1f}c)")
    print(f"\n  VERDICT: {verdict}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    if mode == "snapshot":
        snapshot()
    elif mode == "settle":
        settle()
    elif mode == "report":
        report()
    else:
        print("usage: wx_earlylock_forward.py [snapshot|settle|report]")


if __name__ == "__main__":
    main()
