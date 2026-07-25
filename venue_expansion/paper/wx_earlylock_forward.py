#!/usr/bin/env python3
"""wx_earlylock_forward.py -- READ-ONLY / PAPER forward PRICE-LOGGER for the "early-lock" refinement.

WHY: wx_earlylock_study.py PROVED the PREDICTABILITY half of early-lock -- at threshold 0.95 a per-station
diurnal climatology calls daily-HIGH strike clearance a median ~60 min BEFORE the mechanical lock at ~96.88%
pooled win. But predictability alone does NOT decide deployment. The deployed mechanical-lock baseline buys the
same rung at ~98c (~99.6% win, EV ~+1.1c/ct). An early rung at 96.88% win only BEATS that baseline if it can be
bought <= ~95.3c (break-even); at <=92c EV roughly quadruples. Whether the LIVE market actually offers those
early rungs that cheap -- or has already priced the same forecast to >=96c ("dead") -- is UNKNOWN from backtest.
This harness MEASURES it, paper-only, by logging the real yes-ask at each early-lock signal moment:

  snapshot : one live pass. For each active daily-HIGH *and* daily-LOW city today (the study covers BOTH
             mirrors), pull the current observed running extreme the exact way kwx_runner does
             (feed_for_station), and for each YES-side rung -- floor-only "X>strike" for highs, cap-only
             "X<strike" for lows (exactly the sides kwx_runner.locked_orders buys YES on) -- compute the
             early-lock signal from the PERSISTED fixed climatology:
             predicted_final = running_extreme + E[remaining_change | current LST bin] (remaining RISE for
             highs, remaining FALL for lows); P_clear = P(final > strike) [sf] for highs, P(final < strike)
             [cdf] for lows, under Normal(predicted_final, resid_std). If P_clear >= 0.95 AND the mechanical
             lock has NOT yet fired (the running extreme has not cleared strike-with-margin), log ONE paper
             row capturing the live yes_ask.
             Idempotent per (ticker, date). No orders, no look-ahead: settlement is scored later from IEM ASOS.
  settle   : for logged rows whose LST day has passed, fetch the realized official ASOS daily max/min from IEM,
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
# The threshold/break-even numbers were derived on the HIGH case; the LOW mirror reuses them unchanged so the
# two sleeves stay directly comparable (the LOW study's own frontier is reported in its PR/run output).
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
    """Load the persisted FIXED climatology (fast, no refetch). If missing -- or if it's a pre-LOW file that
    only carries the HIGH map -- build/rebuild it once via the study (build_fixed_climatology reads
    ./_earlylock_cache and writes _earlylock_climatology.json with BOTH the 'stations' HIGH map and the
    'stations_low' LOW map; the HIGH schema/key is unchanged so old consumers keep working)."""
    if not os.path.exists(CLIMO):
        if verbose:
            print(f"climatology {CLIMO} missing -> building once from cache (this may fetch if cache is cold)...")
        S.build_fixed_climatology(verbose=verbose)
    with open(CLIMO) as f:
        climo = json.load(f)
    if "stations_low" not in climo:
        if verbose:
            print("climatology is HIGH-only (pre-LOW schema) -> rebuilding once to add the LOW map...")
        climo = S.build_fixed_climatology(verbose=verbose)
    return climo


# ---------------- snapshot ----------------
def snapshot(verbose=True):
    """One live pass, BOTH cases. For each active daily-HIGH (kind='max') and daily-LOW (kind='min') city,
    read the current running extreme (the runner's feed path) and, per YES-side rung (floor-only 'X>strike'
    for highs, cap-only 'X<strike' for lows), compute P_clear from the persisted climatology. Log ONE paper
    row per rung when P_clear >= THR AND the mechanical lock has NOT yet fired. Idempotent on (ticker, date)."""
    climo = load_climatology(verbose=verbose)
    # per-kind climatology maps: 'stations' (HIGH, remaining rise >= 0) is the original key -- unchanged for
    # backward compat -- and 'stations_low' (LOW, remaining fall <= 0) is the mirror added alongside it.
    maps = {"max": climo.get("stations", {}), "min": climo.get("stations_low", {})}
    seen = {(r["ticker"], r["date"]) for r in _load_jsonl(PAPER)}
    now_utc = dt.datetime.now(tz=dt.timezone.utc)
    n_events = {"max": 0, "min": 0}   # events with a live ladder + a running extreme, per kind
    n_rows = 0
    examples = []
    fout = open(PAPER, "a")
    for series, ev, station, offset, lst_date, kind in R.active_market_days():
        binmap = maps.get(kind, {}).get(station)
        if not binmap:             # no persisted climatology for this station+kind -> can't signal; skip
            continue
        rungs = R.event_rungs(ev)
        if not rungs:
            continue
        # current observed running extreme, obtained the SAME way the live runner does (feed_for_station +
        # sustain filter). kind is threaded through, so 'min' returns the running MIN exactly as the runner sees it.
        try:
            feed = R.feed_for_station(station).running_extreme(station, lst_date, offset, kind)
        except Exception as e:
            if verbose:
                print(f"  [feed skip] {station} {kind}: {type(e).__name__}")
            continue
        if not feed:
            continue
        running_ext = R.sustained_extreme(feed.get("obs") or [], kind)
        if running_ext is None:
            running_ext = feed.get("extreme_f")
        if running_ext is None:
            continue
        running_ext = float(running_ext)
        # current LST minute-of-day -> climatology bin -> (E[remaining_change], resid_std). For 'max' the mean
        # change is the expected remaining RISE (>=0); for 'min' the expected remaining FALL (<=0). Either way
        # predicted_final = running + mean_chg, so the same two lines serve both mirrors.
        now_local = now_utc + dt.timedelta(hours=offset)
        lst_min = now_local.hour * 60 + now_local.minute
        est = binmap.get(str(lst_min // BIN))
        if not est:                # no climatology for this bin (too few sample days there) -> skip
            continue
        mean_chg, resid_std = float(est[0]), float(est[1])
        predicted_final = running_ext + mean_chg
        st_margin = R.STATION_MARGIN.get(station, R.MARGIN_F)   # same per-station margin the runner locks on
        n_events[kind] += 1
        for r in rungs:
            floor, cap = r.get("floor"), r.get("cap")
            # the early-lock signal is the YES side the deployed mechanical-lock buys (kwx_runner.locked_orders):
            #   max: floor-only "X > floor" rung -> YES once max clears floor+margin
            #   min: cap-only  "X < cap"  rung -> YES once min clears cap-margin
            # Skip range rungs and the wrong-side single-strike rungs (not the study's swept case).
            if kind == "max":
                if cap is not None or floor is None:
                    continue
                strike = floor
            else:
                if floor is not None or cap is None:
                    continue
                strike = cap
            yes_ask_c = r.get("yes_ask_c")
            if not yes_ask_c:      # no live yes offer -> nothing to price-capture; skip
                continue
            # mechanical-lock GATE: only log a GENUINELY-EARLY signal -- one fired BEFORE the running extreme
            # cleared strike-with-margin (once it clears, the deployed bot already buys it; no earlier entry).
            # NB the mirror asymmetry: a running max only ever RISES, a running min only ever FALLS, so
            # "already locked" is above floor+margin for highs and below cap-margin for lows.
            if kind == "max":
                if running_ext > strike + st_margin:
                    continue
                p_clear = float(norm.sf(strike, predicted_final, resid_std))    # P(final daily max > strike)
                deg_to_strike = strike - running_ext    # >0 = temp still BELOW strike (genuinely predictive)
            else:
                if running_ext < strike - st_margin:
                    continue
                p_clear = float(norm.cdf(strike, predicted_final, resid_std))   # P(final daily min < strike)
                deg_to_strike = running_ext - strike    # >0 = temp still ABOVE strike (genuinely predictive)
            if p_clear < THR:
                continue
            k = (r["ticker"], lst_date)
            if k in seen:          # idempotent per (ticker, date): never double-log a rung the same day
                continue
            seen.add(k)
            row = {
                "ts": now_utc.isoformat(), "date": lst_date, "city": series, "station": station,
                "kind": kind, "ticker": r["ticker"], "strike": strike,
                "running_ext": round(running_ext, 2), "predicted_final": round(predicted_final, 2),
                "mean_chg": round(mean_chg, 3), "resid_std": round(resid_std, 3),
                "p_clear": round(p_clear, 4), "yes_ask_c": yes_ask_c,
                "deg_to_strike": round(deg_to_strike, 2),   # >0 = temp still short of strike (predictive)
                "lst_min": lst_min, "margin": st_margin, "thr": THR,
            }
            fout.write(json.dumps(row) + "\n")
            n_rows += 1
            if len(examples) < 10:
                examples.append(row)
    fout.close()
    if verbose:
        print(f"snapshot: {n_events['max']} daily-HIGH + {n_events['min']} daily-LOW events with "
              f"ladder+running-extreme, {n_rows} new early-lock paper rows (P_clear>={THR}, "
              f"pre-mechanical-lock) -> {PAPER}")
        for r in examples:
            print(f"  {r['city']:<11} {r['station']:<4} {r['kind']:<3} strike={r['strike']:<3} "
                  f"run={r['running_ext']:.1f} pred={r['predicted_final']:.1f} p_clear={r['p_clear']:.3f} "
                  f"yes_ask={r['yes_ask_c']}c (temp {r['deg_to_strike']:+.1f}F to strike)")
    return n_rows


# ---------------- settle ----------------
def _iem_daily_extreme(station, date_iso, kind="max"):
    """Realized official ASOS daily max_temp_f (kind='max') or min_temp_f (kind='min') for a station on a
    local date, or None. Copies wx_forecast_forward._iem_daily (IEM daily.py, comma format); the query already
    requested BOTH vars, so the LOW case just reads the other column of the same response."""
    net = M.STATIONS[station][3]
    stid = M.iem_station(station)
    y, m, d = date_iso.split("-")
    q = (f"?network={net}&stations={stid}&year1={y}&month1={int(m)}&day1={int(d)}"
         f"&year2={y}&month2={int(m)}&day2={int(d)}&var=max_temp_f,min_temp_f&format=comma")
    try:
        txt = _get_text(IEM + q)
    except Exception:
        return None
    col = "max_temp_f" if kind == "max" else "min_temp_f"
    for row in csv.DictReader(io.StringIO(txt)):
        if row.get("day") == date_iso:
            try:
                return float(row.get(col))
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
        kind = r.get("kind", "max")   # rows logged before the LOW mirror existed carry no 'kind' -> HIGH
        tk = (r["station"], r["date"], kind)
        if tk not in truth:
            truth[tk] = _iem_daily_extreme(r["station"], r["date"], kind)
        realized = truth[tk]
        if realized is None:
            continue   # not yet available -> retry next run
        # YES wins iff the realized daily extreme cleared the strike: max above it ("X > strike"), min below
        # it ("X < strike") -- the exact mirror of the runner's lock sides.
        cleared = (realized > r["strike"]) if kind == "max" else (realized < r["strike"])
        price = r["yes_ask_c"] / 100.0           # paper entry at the LOGGED live ask (the whole point of the test)
        fee = _kalshi_fee(price)
        pnl = (1.0 - price - fee) if cleared else (-price - fee)
        rec = {**r, "kind": kind, "realized_ext": realized, "cleared": cleared, "won": cleared,
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
        print("no settled rows yet. Run `snapshot` during US afternoon rising-temp windows (highs) and the")
        print("overnight/pre-dawn falling windows (lows) to log early-lock paper rows, then `settle` after")
        print("each day ends.")
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

    # per-kind split (HIGH vs LOW mirror) -- the LOW sleeve is newer, so watch its numbers separately before
    # trusting the pooled verdict. Pre-LOW rows carry no 'kind' field -> HIGH.
    bykind = defaultdict(list)
    for r in rows:
        bykind[r.get("kind", "max")].append(r)
    if len(bykind) > 1 or "min" in bykind:
        print("\n  by case (HIGH=max / LOW=min):")
        for kd in ("max", "min"):
            s = bykind.get(kd)
            if s:
                print(f"    {kd:<4} n={len(s):<4} win={sum(1 for r in s if r['won'])/len(s):.1%} "
                      f"mean_ask={stt.mean([r['yes_ask_c'] for r in s]):.1f}c "
                      f"EV/ct={stt.mean([r['pnl'] for r in s])*100:+.2f}c")

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
