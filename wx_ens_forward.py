#!/usr/bin/env python3
"""wx_ens_forward.py -- costless, PAPER-ONLY FORWARD collector for the true 51-member ECMWF ensemble
(Open-Meteo `ensemble-api.open-meteo.com`) vs live Kalshi weather markets.

WHY A FORWARD-ONLY LOGGER (not a backtest): wx_forecast_model.py already tests the *deterministic*
Open-Meteo forecast (one point value per city-day) against Kalshi and that has its own forward harness
(wx_forecast_forward.py). The 51-member ENSEMBLE is a materially different signal -- it gives a full
empirical distribution of the daily extreme, not just a point forecast, so "P(clears strike)" can be
read directly as a member-fraction instead of assumed-Normal from a point + a fitted residual std. But
Open-Meteo's ensemble endpoint only retains ~92h of history server-side (confirmed 2026-07-23) -- there
is no way to pull "what did the 51-member ensemble say 3 weeks ago" -- so this edge CANNOT be backtested.
It can only be measured going forward: log the live ensemble's P(clears strike) next to the live Kalshi
price at snapshot time, then independently settle later. That is exactly the shape of the earlylock/
forecast sibling harnesses (wx_earlylock_forward.py, wx_forecast_forward.py); this module mirrors their
structure and accounting so the three forward sleeves stay directly comparable.

  snapshot : for each of the ~20 Kalshi weather cities (kwx_runner.CITY station/offset map, read-only),
             pull the CURRENT live ECMWF 51-member ensemble (temperature_2m control + member01..member50)
             for the station's LST day, compute each member's daily EXTREME (max for KXHIGH*, min for
             KXLOWT*) over that day's populated local hours, then for every ACTIVE Kalshi weather market
             on that city+kind (kwx_runner.event_rungs, fetched live) parse its strike(s) and compute
             ensemble_P = fraction of the 51 members (each rounded to the nearest integer degF, matching
             Kalshi's integer NWS CLI settlement) whose daily extreme satisfies the market's YES condition --
             floor-only "X>floor", cap-only "X<cap", or the INCLUSIVE "floor<=X<=cap" bucket for a middle
             rung; see ensemble_prob_yes's docstring for the live-verified settlement convention (this is
             NOT the same as kwx_runner.locked_and_misses' margin-padded lock test, which never exercises an
             exact boundary and was never a valid source for the settlement convention). Read the live
             yes_ask/no_ask; if the ensemble disagrees with whichever side is cheaper to buy by more than
             EDGE_THR (pre-registered, see below), log ONE paper candidate, INCLUDING a rounded-integer
             histogram of all 51 members' extremes (member_hist) so the row can be re-scored later without
             needing to re-fetch (impossible anyway, given the ~92h ensemble history window).
             NO ORDERS -- logging only. Idempotent per ticker (a market only ever gets one candidate row).
  settle   : for logged candidates whose market has resolved, fetch the true result via the live public
             Kalshi API (GET /markets/{ticker}, status=="finalized", result in {"yes","no"} -- same
             endpoint kx_history.py's hist_* functions wrap for the older/paginated case; a market still
             inside the ~3-month live window resolves directly off /markets/{ticker}, which is all this
             forward logger will ever need since it only settles candidates it logged itself, all recent).
             Score pnl at the LOGGED entry_price_c net of the Kalshi taker fee ceil(7*p*(1-p))/100 (CLAUDE.md
             fee rule == kwx_runner._kalshi_fee_c), with correct BOTH-side accounting: a NO position's
             payoff on a win is (100 - entry_price_c) cents (NOT 100), because a NO contract's notional is
             the no_ask paid, same $1 payout structure as YES, just priced from the other side.
  decision : see wx_ens_decision.py (separate module, reads wx_ens_settled.jsonl only).

NO LOOK-AHEAD: every paper row's `ensemble_run_time` is the UTC instant the ensemble HTTP response was
received (a deliberately CONSERVATIVE proxy for the ECMWF model's actual init/cycle time, which Open-Meteo's
API response does not expose -- using fetch-time instead of init-time only ever makes the logged instant
LATER than the true forecast issuance, which is the safe direction: it can never look further into the
future than it honestly could have). `ts` is the wall-clock instant the row was written. Both strictly
precede the market's `date` (LST calendar day) resolving, and `settle()` refuses to score a row until that
LST date is safely in the past (see the same-day guard below) -- so no settled row can ever have been scored
before its own outcome existed.

HARD SAFETY: read-only public APIs only (Open-Meteo ensemble + Kalshi public REST). Never imports or calls
kwx_runner's execution path, kalshi_exec.py, kwx_paper_gate.py; never sets/reads KWX_LIVE; never places an
order. Only touches kwx_runner.py to READ its CITY/CITY_LOW_SERIES/active_market_days/event_rungs (frozen,
unmodified) for the station map and the live ladder.

Usage:
    python wx_ens_forward.py snapshot   # one live pass -> log paper rows to wx_ens_paper.jsonl
    python wx_ens_forward.py settle     # score resolved candidates -> wx_ens_settled.jsonl
"""
import io
import json
import math
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.environ.get("KWX_REPO_DIR", "/home/user/Codex-playground-")
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

import kwx_runner as R          # noqa: E402  -- READ-ONLY: only CITY / CITY_LOW_SERIES / active_market_days /
import wx_forecast_model as M   # noqa: E402  -- event_rungs are used; nothing in kwx_runner is imported for
                                 # its execution path (kalshi_exec / paper_gate are never touched).

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None

ENS_BASE = "https://ensemble-api.open-meteo.com/v1/ensemble"
KBASE = "https://api.elections.kalshi.com/trade-api/v2"

PAPER = os.path.join(HERE, "wx_ens_paper.jsonl")
SETTLED = os.path.join(HERE, "wx_ens_settled.jsonl")

# ---------------- pre-registered activation knobs (frozen BEFORE any settled data is read) ----------------
# EDGE_THR: minimum |ensemble_P - kalshi_price| (probability units, i.e. cents/100) to log a candidate.
# Derivation: with n=51 ensemble members, the sampling SE of a member-fraction estimate at the most
# conservative point p=0.5 is sqrt(0.5*0.5/51) ~= 0.070. A threshold of 2x that SE (~0.14) is the point past
# which a raw disagreement is unlikely to be pure ensemble-sampling noise, independent of any backtest (which
# is impossible here -- see module docstring). Rounded to 0.15 to match the sibling forward harness's own
# pre-registered EDGE_THR (wx_forecast_forward.EDGE_THR = 0.15), so all three forward sleeves use the same
# bar and stay directly comparable.
EDGE_THR = 0.15
N_MEMBERS_EXPECTED = 51        # control (temperature_2m) + member01..member50


def _kalshi_fee_c(price_c):
    """Kalshi taker fee in CENTS/contract: ceil(7*p*(1-p))/100 dollars per CLAUDE.md, i.e.
    ceil(0.07*p*(1-p)*100) whole cents -- identical formula/rounding to kwx_runner._kalshi_fee_c and
    wx_forecast_forward._kalshi_fee (kept in whole cents here to match entry_price_c's units)."""
    p = price_c / 100.0
    return math.ceil(0.07 * p * (1 - p) * 100)


def _load_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _get_json(url, to=30):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=to, context=_CTX) as h:
        return json.loads(h.read().decode())


# ---------------- ensemble fetch + per-member daily extreme ----------------
def _member_keys(hourly):
    """All temperature_2m* series in the response: control 'temperature_2m' + 'temperature_2m_memberNN'."""
    return [k for k in hourly.keys() if k == "temperature_2m" or k.startswith("temperature_2m_member")]


def fetch_ensemble_extremes(station, lst_date, kind, verbose=False):
    """Pull the CURRENT live 51-member ECMWF ensemble for `station` and return (extremes, ensemble_run_time,
    n_members_total) where extremes is a list of per-member daily max (kind='max') or min (kind='min') over
    the station's LST day `lst_date` (YYYY-MM-DD), using only POPULATED (non-null) local hours for that date
    -- Open-Meteo nulls some hours at the forecast window's edges, so a member that has zero populated hours
    for the target date is silently dropped from the list (not padded/imputed) rather than counted as a
    spuriously-narrow member. Returns (None, None, 0) if the station is unknown or the date isn't in range."""
    if station not in M.STATIONS:
        return None, None, 0
    lat, lon, tz, _ = M.STATIONS[station]
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "models": "ecmwf_ifs025",
        "hourly": "temperature_2m", "temperature_unit": "fahrenheit",
        "timezone": tz, "forecast_days": 2,
    })
    try:
        d = _get_json(f"{ENS_BASE}?{q}")
    except Exception as e:
        if verbose:
            print(f"  [ensemble fetch fail] {station}: {type(e).__name__}: {e}")
        return None, None, 0
    now_utc = dt.datetime.now(tz=dt.timezone.utc)
    hourly = d.get("hourly") or {}
    times = hourly.get("time") or []
    mkeys = _member_keys(hourly)
    idx = [i for i, t in enumerate(times) if t.startswith(lst_date)]
    if not idx or not mkeys:
        return [], now_utc.isoformat(), 0
    extremes = []
    for mk in mkeys:
        vals = hourly.get(mk) or []
        day_vals = [vals[i] for i in idx if i < len(vals) and vals[i] is not None]
        if not day_vals:
            continue   # this member has no populated hours for the date (edge-of-window nulls) -> drop it
        extremes.append(max(day_vals) if kind == "max" else min(day_vals))
    return extremes, now_utc.isoformat(), len(mkeys)


# ---------------- Kalshi-convention YES probability from the ensemble ----------------
def ensemble_prob_yes(extremes, kind, floor, cap):
    """P(YES) implied by the ensemble member fraction, under Kalshi's ACTUAL settlement convention
    (verified live against the API's strike_type field on KXHIGH*/KXLOWT* rungs -- NOT the same convention
    as wx_forecast_model.bracket_prob's docstring or kwx_runner.locked_and_misses' MARGIN-padded lock test,
    neither of which is a settlement-boundary spec: locked_and_misses only ever fires with margin>=1.0degF
    and never has to resolve an exact-boundary case, so its convention was never actually exercised there).

    Kalshi settles on the INTEGER NWS CLI daily extreme, so each member's raw (possibly fractional) daily
    extreme is first rounded to the nearest integer degF, THEN compared:
      both floor and cap set (a "between" bucket)  : YES = "floor <= X <= cap"   (INCLUSIVE of both ends,
                                                       e.g. an '88 to 89' rung settles YES for X in {88,89})
      floor-only, cap is None ("greater")          : YES = "X > floor"           (i.e. X >= floor+1)
      cap-only, floor is None ("less")             : YES = "X < cap"             (i.e. X <= cap-1)
    This holds IDENTICALLY for kind='max' (KXHIGH*) and kind='min' (KXLOWT*) -- the comparison is against
    the settled integer value itself, not dependent on whether that value is a daily max or min, so there is
    no kind-conditional branch here (an earlier draft wrongly used a stricter/looser mirror per kind and a
    non-inclusive bucket bound; both are corrected here per a live-verified adversarial review).
    Returns None if extremes is empty or neither strike is set."""
    n = len(extremes)
    if n == 0 or (floor is None and cap is None):
        return None
    settled = [round(v) for v in extremes]
    if floor is not None and cap is not None:
        c = sum(1 for v in settled if floor <= v <= cap)
    elif floor is not None:
        c = sum(1 for v in settled if v > floor)
    else:
        c = sum(1 for v in settled if v < cap)
    return c / n


# ---------------- snapshot ----------------
def snapshot(verbose=True):
    """One live pass over every active Kalshi weather city+kind. Logs at most one paper candidate per
    ticker (idempotent on ticker alone -- a given market ticker is unique to one city/day/strike and only
    ever needs one logged entry/exit price)."""
    seen = {r["ticker"] for r in _load_jsonl(PAPER)}
    ens_cache = {}   # (station, lst_date, kind) -> (extremes, ensemble_run_time, n_total)
    n_events = 0     # city+kind events that had a live ladder AND a usable ensemble pull
    n_markets_checked = 0
    n_rows = 0
    examples = []
    fout = open(PAPER, "a")
    for series, ev, station, offset, lst_date, kind in R.active_market_days():
        rungs = R.event_rungs(ev)
        if not rungs:
            continue
        ck = (station, lst_date, kind)
        if ck not in ens_cache:
            ens_cache[ck] = fetch_ensemble_extremes(station, lst_date, kind, verbose=verbose)
        extremes, ens_run_time, n_total = ens_cache[ck]
        if not extremes:
            continue
        n_events += 1
        now_utc = dt.datetime.now(tz=dt.timezone.utc)
        for r in rungs:
            if r["ticker"] in seen:
                continue
            floor, cap = r.get("floor"), r.get("cap")
            n_markets_checked += 1
            p_yes = ensemble_prob_yes(extremes, kind, floor, cap)
            if p_yes is None:
                continue
            yes_ask_c, no_ask_c = r.get("yes_ask_c"), r.get("no_ask_c")
            # pick whichever side has BOTH a live ask AND the larger ensemble-vs-market edge
            cand = None
            if yes_ask_c:
                edge = p_yes - yes_ask_c / 100.0
                if edge > EDGE_THR and (cand is None or edge > cand[1]):
                    cand = ("yes", edge, yes_ask_c)
            if no_ask_c:
                edge = (1.0 - p_yes) - no_ask_c / 100.0
                if edge > EDGE_THR and (cand is None or edge > cand[1]):
                    cand = ("no", edge, no_ask_c)
            if cand is None:
                continue
            side, edge, entry_price_c = cand
            fee_c = _kalshi_fee_c(entry_price_c)
            strike = floor if floor is not None else cap
            # Persist a rounded-integer histogram of the 51 member extremes (not just the scalar ensemble_P)
            # so the forward record can be RE-SCORED if the probability convention is ever corrected or
            # questioned again -- losing the raw member distribution would make 30 days of irreplaceable
            # forward data unrecoverable to any future scoring fix (this is exactly what happened once already:
            # see ensemble_prob_yes's docstring). Keyed by str(int) since JSON object keys must be strings.
            hist = {}
            for v in extremes:
                iv = round(v)
                hist[str(iv)] = hist.get(str(iv), 0) + 1
            row = {
                "ts": now_utc.isoformat(), "ensemble_run_time": ens_run_time,
                "ticker": r["ticker"], "event": ev, "city": series, "station": station,
                "kind": kind, "date": lst_date, "floor": floor, "cap": cap, "strike": strike,
                "ensemble_P": round(p_yes, 4), "n_members": len(extremes), "n_members_total": n_total,
                "member_hist": hist,   # {rounded_int_degF: count} over all n_members -- re-scoring source of truth
                "kalshi_side": side, "entry_price_c": entry_price_c, "fee_c": fee_c,
                "yes_ask_c": yes_ask_c, "no_ask_c": no_ask_c,  # both raw asks, for a fair market-implied
                                                                # P(yes) at settle/decision time (Brier compare)
                "edge": round(edge, 4), "thr": EDGE_THR,
            }
            fout.write(json.dumps(row) + "\n")
            seen.add(r["ticker"])
            n_rows += 1
            if len(examples) < 12:
                examples.append(row)
    fout.close()
    if verbose:
        print(f"snapshot: {n_events} city+kind events with a live ladder + usable ensemble pull, "
              f"{n_markets_checked} markets scored, {n_rows} new paper candidates "
              f"(|ensemble_P - price| > {EDGE_THR}) -> {PAPER}")
        for r in examples:
            fc = r["floor"] if r["floor"] is not None else "-"
            cc = r["cap"] if r["cap"] is not None else "-"
            print(f"  {r['city']:<11} {r['station']:<4} {r['kind']:<3} floor={fc}/cap={cc}  "
                  f"ens_P={r['ensemble_P']:.3f} {r['kalshi_side']:>3}_ask={r['entry_price_c']}c "
                  f"edge={r['edge']:+.3f} n_mem={r['n_members']} [{r['ticker']}]")
    return n_rows


# ---------------- settle ----------------
def _kalshi_market(ticker):
    try:
        d = _get_json(f"{KBASE}/markets/{ticker}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return d.get("market")


def settle(verbose=True):
    rows = _load_jsonl(PAPER)
    already = {r["ticker"] for r in _load_jsonl(SETTLED)}
    today_utc = dt.datetime.now(tz=dt.timezone.utc).date()
    n_new, n_skipped_not_final = 0, 0
    fout = open(SETTLED, "a")
    for r in rows:
        tk = r["ticker"]
        if tk in already:
            continue
        try:
            d = dt.date.fromisoformat(r["date"])
        except Exception:
            continue
        if d >= today_utc:      # LST day not safely over yet -- never settle before the outcome could exist
            continue
        m = _kalshi_market(tk)
        if not m or m.get("status") != "finalized" or m.get("result") not in ("yes", "no"):
            n_skipped_not_final += 1
            continue            # market not yet resolved on the public API -- retry next run
        result = m["result"]
        side = r["kalshi_side"]
        won = (result == side)
        price = r["entry_price_c"] / 100.0
        fee = r["fee_c"] / 100.0
        # BOTH-side accounting: a win pays $1 total notional regardless of side; pnl = payoff - entry - fee.
        # (1 - price) is identical whether the entry was a yes_ask or a no_ask -- the $1 payout minus whatever
        # was paid to enter -- so this one formula is already correct for both sides; a loss simply pays 0.
        pnl = (1.0 - price - fee) if won else (-price - fee)
        rec = {**r, "result": result, "won": won, "pnl": round(pnl, 4)}
        fout.write(json.dumps(rec) + "\n")
        already.add(tk)
        n_new += 1
    fout.close()
    if verbose:
        print(f"settled {n_new} new candidates ({n_skipped_not_final} checked but not yet finalized) -> {SETTLED}")
    return n_new


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if mode == "snapshot":
        snapshot()
    elif mode == "settle":
        settle()
    else:
        print("usage: wx_ens_forward.py [snapshot|settle]")


if __name__ == "__main__":
    main()
