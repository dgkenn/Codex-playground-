#!/usr/bin/env python3
"""wx_forecast_forward.py -- FORWARD paper-validation harness for the Kalshi FORECAST temp edge.

WHY: wx_forecast_model.py turns a free Open-Meteo forecast into P(settlement in each Kalshi bracket). The open
question is whether that forecast_prob beats the market's yes-price -- the market makers see the same forecast,
so a positive, +EV gap is NOT guaranteed and must be MEASURED, not assumed. This harness does the measuring,
paper-only:

  snapshot : for every active city+kind today, pull the live ladder (kwx_runner.event_rungs) + the current
             forecast, compute forecast_prob vs the market yes-price per rung, and log a PAPER trade wherever
             |forecast_prob - price| >= EDGE_THR (buy YES if fc_prob-price>=thr, buy NO if price-fc_prob>=thr).
             No look-ahead: the forecast is fetched and logged at snapshot time; settlement is scored later
             from independent ASOS truth. Idempotent per (ticker, side, date).
  settle   : for logged rows whose local settlement date has passed, fetch the realized official ASOS daily
             max/min from IEM, decide the bracket outcome, and compute paper pnl/contract net of the Kalshi
             fee (same ceil(0.07*p*(1-p)) formula the nowcast harness uses).
  report   : from settled rows, print n / win% / EV per contract / day-clustered t, a CALIBRATION table
             (forecast_prob deciles: predicted vs realized frequency -- the honesty check on the model), and
             whether forecast_prob-price actually predicts pnl (edge-decile pnl), split YES vs NO.

PROPOSE-ONLY / PAPER: never places orders, never touches credentials, never calls live-trading code. Reads
public Kalshi + Open-Meteo + IEM, writes two jsonl logs. stdlib + numpy/scipy only. TLS via session CA.

Usage:
    python wx_forecast_forward.py snapshot   # one live snapshot -> log paper rows to wx_forecast_paper.jsonl
    python wx_forecast_forward.py settle     # score rows whose day has passed -> wx_forecast_settled.jsonl
    python wx_forecast_forward.py report     # stats + calibration + edge-vs-pnl honesty check
"""
import os, ssl, sys, json, math, io, csv, datetime as dt, urllib.request
from collections import defaultdict

import kwx_runner as R
import wx_forecast_model as M

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
PAPER = os.path.join(HERE, "wx_forecast_paper.jsonl")
SETTLED = os.path.join(HERE, "wx_forecast_settled.jsonl")

EDGE_THR = 0.15   # min |forecast_prob - yes_price| (in probability units) to log a paper trade


def _get_text(url, to=30):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "text/plain"}), timeout=to, context=_CTX).read().decode()


def _kalshi_fee(price_dollars):
    """Standard Kalshi quadratic fee (multiplier 1), rounded up to the cent per contract -- identical to
    kwx_forward._kalshi_fee so paper pnl matches the nowcast sleeve's accounting."""
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


# ---------------- snapshot ----------------
def snapshot(verbose=True):
    """One live pass: for each active city+kind, fetch forecast + ladder, log paper trades on rungs where the
    forecast disagrees with the market yes-price by >= EDGE_THR. Idempotent on (ticker, side, date)."""
    seen = {(r["ticker"], r["side"], r["date"]) for r in _load_jsonl(PAPER)}
    n_cities = 0        # city+kind events that had a live ladder
    n_rows = 0
    examples = []
    fc_cache = {}       # (station, date) -> forecast dict (one Open-Meteo call per station-day)
    fout = open(PAPER, "a")
    for series, ev, station, offset, lst_date, kind in R.active_market_days():
        rungs = R.event_rungs(ev)
        if not rungs:
            continue
        # forecast for THIS station's local settlement date (lst_date). Cache per station-day.
        key = (station, lst_date)
        if key not in fc_cache:
            try:
                fc_cache[key] = M.fetch_forecast(station, date=lst_date)
            except Exception as e:
                if verbose:
                    print(f"  [forecast skip] {station} {lst_date}: {type(e).__name__}")
                fc_cache[key] = None
        fc = fc_cache[key]
        if not fc:
            continue
        n_cities += 1
        mu = fc["max"] if kind == "max" else fc["min"]
        sigma = M.predictive_sigma(kind, fc["lead_days"])
        for r in rungs:
            price_c = r.get("yes_ask_c")
            if not price_c:            # no live yes offer -> can't price the edge; skip
                continue
            price = price_c / 100.0
            fc_prob = M.bracket_prob(r.get("floor"), r.get("cap"), mu, sigma)
            edge = fc_prob - price
            if abs(edge) < EDGE_THR:
                continue
            side = "yes" if edge >= 0 else "no"
            k = (r["ticker"], side, lst_date)
            if k in seen:
                continue
            seen.add(k)
            row = {
                "date": lst_date, "series": series, "station": station, "kind": kind,
                "ticker": r["ticker"], "lo": r.get("floor"), "hi": r.get("cap"),
                "mu": round(mu, 2), "sigma": round(sigma, 3),
                "fc_prob": round(fc_prob, 4), "price": round(price, 4),
                "side": side, "edge": round(edge, 4),
                "issued": fc["issued"], "lead_days": fc["lead_days"],
                "ts": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
            }
            fout.write(json.dumps(row) + "\n")
            n_rows += 1
            if len(examples) < 8:
                examples.append(row)
    fout.close()
    if verbose:
        print(f"snapshot: {n_cities} city+kind events with ladders, {n_rows} new paper rows -> {PAPER}")
        for r in examples:
            rung = f"({r['lo']},{r['hi']}]"
            print(f"  {r['series']:<11} {r['station']:<4} {r['kind']:<3} {rung:<12} "
                  f"mu={r['mu']:.1f} fc_prob={r['fc_prob']:.3f} price={r['price']:.3f} "
                  f"edge={r['edge']:+.3f} -> BUY {r['side'].upper()}")
    return n_rows


# ---------------- settle ----------------
def _iem_daily(station, date_iso):
    """Realized official ASOS (max_temp_f, min_temp_f) for a station on a local date, or (None,None)."""
    _, _, _, net = M.STATIONS[station]
    stid = M.iem_station(station)
    y, m, d = date_iso.split("-")
    q = (f"?network={net}&stations={stid}&year1={y}&month1={int(m)}&day1={int(d)}"
         f"&year2={y}&month2={int(m)}&day2={int(d)}&var=max_temp_f,min_temp_f&format=comma")
    try:
        txt = _get_text(IEM + q)
    except Exception:
        return None, None
    rows = list(csv.DictReader(io.StringIO(txt)))
    for row in rows:
        if row.get("day") == date_iso:
            def _f(v):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
            return _f(row.get("max_temp_f")), _f(row.get("min_temp_f"))
    return None, None


def _bracket_won(lo, hi, settle_val):
    """Did rung (floor=lo, cap=hi) settle YES given the realized whole-degF value? Mirrors Kalshi '>' convention:
    cap-only -> X <= cap; top rung -> X > floor; full bracket -> floor < X <= cap."""
    if lo is not None and not (settle_val > lo):
        return False
    if hi is not None and not (settle_val <= hi):
        return False
    return True


def settle(verbose=True):
    rows = _load_jsonl(PAPER)
    already = {(r["ticker"], r["side"], r["date"]) for r in _load_jsonl(SETTLED)}
    truth = {}   # (station, date) -> (max, min); cache IEM calls
    today_utc = dt.datetime.now(tz=dt.timezone.utc).date()
    n_new = 0
    fout = open(SETTLED, "a")
    for r in rows:
        key3 = (r["ticker"], r["side"], r["date"])
        if key3 in already:
            continue
        # only settle once the local day is fully over (settlement date strictly before today's UTC date is a
        # safe, simple no-look-ahead bound; ASOS daily is finalized after local midnight).
        try:
            d = dt.date.fromisoformat(r["date"])
        except Exception:
            continue
        if d >= today_utc:
            continue
        tk = (r["station"], r["date"])
        if tk not in truth:
            truth[tk] = _iem_daily(r["station"], r["date"])
        mx, mn = truth[tk]
        realized = mx if r["kind"] == "max" else mn
        if realized is None:
            continue   # not yet available -> retry next run
        yes_won = _bracket_won(r["lo"], r["hi"], realized)
        won = yes_won if r["side"] == "yes" else (not yes_won)
        price = r["price"]
        fee = _kalshi_fee(price)
        pnl = (1.0 - price - fee) if won else (-price - fee)
        rec = {**r, "realized": realized, "yes_won": yes_won, "won": won, "fee": fee, "pnl": round(pnl, 4)}
        fout.write(json.dumps(rec) + "\n")
        already.add(key3)
        n_new += 1
    fout.close()
    if verbose:
        print(f"settled {n_new} new paper rows -> {SETTLED}")
    return n_new


# ---------------- report ----------------
def _decile(x):
    return min(9, max(0, int(x * 10)))


def report():
    rows = _load_jsonl(SETTLED)
    if not rows:
        print("no settled rows yet. Run `snapshot` daily to log paper trades, then `settle` after the day ends.")
        print(f"(edge threshold in use: |fc_prob - price| >= {EDGE_THR:.2f}; sigma_max={M.SIGMA_MAX}, "
              f"sigma_min={M.SIGMA_MIN})")
        return
    import statistics as stt
    pnls = [r["pnl"] for r in rows]
    n = len(rows)
    wins = sum(1 for r in rows if r["won"])
    byday = defaultdict(list)
    for r in rows:
        byday[r["date"]].append(r["pnl"])
    dm = [stt.mean(v) for v in byday.values()]
    t = (stt.mean(dm) / (stt.stdev(dm) / math.sqrt(len(dm)))) if len(dm) > 1 and stt.stdev(dm) > 0 else float("nan")

    print("=== WX FORECAST FORWARD PAPER (is the forecast edge real?) ===")
    print(f"  n trades       : {n}   ({len(byday)} days)")
    print(f"  win rate       : {wins/n:.1%}")
    print(f"  EV/contract    : {stt.mean(pnls):+.4f}   (net of Kalshi fee)")
    print(f"  day-clustered t: {t:.2f}")
    print(f"  worst / best   : {min(pnls):+.3f} / {max(pnls):+.3f}")

    # YES vs NO split + average edge captured
    for sd in ("yes", "no"):
        s = [r for r in rows if r["side"] == sd]
        if s:
            print(f"  {sd.upper():<3} : n={len(s):<4} win={sum(1 for r in s if r['won'])/len(s):.1%} "
                  f"EV={stt.mean([r['pnl'] for r in s]):+.4f} avg|edge|={stt.mean([abs(r['edge']) for r in s]):.3f}")

    # CALIBRATION: bucket forecast_prob into deciles, predicted (mean fc_prob) vs realized YES-frequency.
    # This is the core honesty check -- a well-calibrated forecast has realized ~= predicted on the diagonal.
    print("\n  CALIBRATION (forecast_prob decile -> predicted vs realized YES-freq):")
    print("    decile    n   pred_fc  realized")
    buck = defaultdict(list)
    for r in rows:
        buck[_decile(r["fc_prob"])].append(r)
    for dcl in range(10):
        b = buck.get(dcl)
        if not b:
            continue
        pred = stt.mean([r["fc_prob"] for r in b])
        realf = stt.mean([1.0 if r["yes_won"] else 0.0 for r in b])
        print(f"    {dcl/10:.1f}-{dcl/10+0.1:.1f}  {len(b):>4}   {pred:.3f}    {realf:.3f}")

    # Does forecast_prob-price actually PREDICT pnl? Bucket by signed edge magnitude, show mean pnl.
    print("\n  EDGE -> PnL (does a bigger fc_prob-price gap earn more? the whole thesis):")
    print("    |edge| bucket    n   mean_pnl")
    ebuck = defaultdict(list)
    for r in rows:
        e = abs(r["edge"])
        b = "0.15-0.25" if e < 0.25 else "0.25-0.40" if e < 0.40 else "0.40+"
        ebuck[b].append(r["pnl"])
    for b in ("0.15-0.25", "0.25-0.40", "0.40+"):
        v = ebuck.get(b)
        if v:
            print(f"    {b:<13} {len(v):>5}   {stt.mean(v):+.4f}")

    verdict = ("EDGE PLAUSIBLE (calibrated + edge earns +EV) -- keep accruing" if stt.mean(pnls) > 0.02 and wins/n > 0.5
               else "NO EDGE VISIBLE (market tracks the forecast; fc_prob-price does not pay)" if stt.mean(pnls) <= 0
               else "INCONCLUSIVE -- need more days")
    print(f"\n  VERDICT: {verdict}")
    if n < 40:
        print("  (n small: not yet decisive; snapshot daily and re-settle.)")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    if mode == "snapshot":
        snapshot()
    elif mode == "settle":
        settle()
    elif mode == "report":
        report()
    else:
        print("usage: wx_forecast_forward.py [snapshot|settle|report]")


if __name__ == "__main__":
    main()
