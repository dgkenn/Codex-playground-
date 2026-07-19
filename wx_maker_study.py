#!/usr/bin/env python3
"""wx_maker_study.py -- ANALYSIS-ONLY harness: would a MAKER variant (resting YES bids at 94-97c on rungs
APPROACHING lock) beat the deployed TAKER (pay the ask ~98c AFTER the mechanical lock, EV ~+1.1c/ct)?

WHY: the deployed bot only TAKES. The books are so thin that paying the ask caps the whole edge. A maker
variant would capture the spread instead of paying it -- IF two unknowns come out favorably: (1) FILL
PROBABILITY (does anyone ever sell into a 94-97c resting bid on a rung that's about to lock?) and (2)
ADVERSE SELECTION (when someone DOES sell to us pre-lock, is it because the rung was about to fail?). Neither
has ever been measured. This module is the measuring instrument, NOT the strategy: it replays logged order-book
snapshots, simulates hypothetical resting bids, scores them against settlement truth, and prints fill-rate /
adverse-selection / EV tables with Wilson CIs. Conclusions are explicitly DATA-DEPENDENT: until the sibling
depth-logger accrues 1-2 weeks of snapshots, `--report` says so instead of pretending.

PROPOSE-ONLY / ANALYSIS-ONLY: this module NEVER places orders, never reads credentials, never imports
kalshi_exec, never touches KWX_SWITCH / .kwx_halt / KWX_LIVE. It reads local jsonl logs + public endpoints.

INPUT 1 -- BOOK SNAPSHOTS (wx_book_snapshots.jsonl, written by the sibling depth-logger unit via
`wx_capacity_probe.py --snapshot`; its schema doc is wx_book_snapshot_schema.md on that unit's branch).
Because the two units run in parallel, the reader here is DEFENSIVE and this docstring is OUR side of the
contract, to be reconciled at merge:

  REQUIRED per line (a JSON dict; non-dict / unparseable lines are skipped and counted):
    ts_utc        : ISO-8601 UTC timestamp of the snapshot ('Z' suffix ok)
    ticker        : Kalshi market ticker, e.g. "KXHIGHDEN-26JUL18-T90"
    yes_bid       : YES bid ladder as [[price_c, count], ...] (resting YES buy interest)
    yes_ask       : YES ask ladder as [[price_c, count], ...] (what a YES buyer can lift)
    best_yes_ask  : best (lowest) YES ask in cents, or null if no offer
                    (derived from the yes_ask ladder if the field itself is absent)
  OPTIONAL (used when present; extra/unknown fields are tolerated and ignored):
    running_extreme_f / running_max / extreme_f / obs_f : the observed running extreme (degF) at snapshot
                    time. NEEDED to decide "approaching lock"; snapshots without it still serve as
                    FILL EVIDENCE (later-ask observations) but cannot trigger a hypothetical placement,
                    and the report counts them so the gap is visible, not silent.
    floor / cap / kind / lst_date : rung strike + market kind + local settlement date; when absent they
                    are parsed from the ticker (T-suffix strike, %y%b%d date, KXHIGH*=max).

INPUT 2 -- SETTLEMENT TRUTH, in priority order (first hit wins):
    (a) kwx_forward_settled.jsonl rows (ticker -> result), already fetched by kwx_forward.py settle
    (b) the public Kalshi market endpoint (same fetch pattern as kwx_forward.settle)
    (c) IEM ASOS daily max as backup truth for HIGH floor rungs (same source wx_earlylock_forward settles on)

WHAT "FILLED" MEANS FROM SNAPSHOTS ALONE (explicit, because we have no private fill feed):
    DEFINITE fill  : some LATER same-day snapshot shows best_yes_ask <= our bid. An ask resting at/below our
                     price can only exist if every bid at/above it was consumed -- ours included. This is the
                     conservative, rigorous criterion (a genuine trade-through).
    AMBIGUOUS fill : best_yes_ask never reached our bid but came within AMBIG_MARGIN_C (default 1c) above it.
                     Prints between snapshots could have hit us; we cannot know. Reported separately so the
                     fill-rate is a BRACKET [definite, definite+ambiguous], never a point estimate.
    NO-FILL        : neither. NOTE the asymmetry: snapshots are sparse, so an ask that flashed through our
                     price BETWEEN snapshots is invisible -> the DEFINITE fill-rate is a lower bound. Queue
                     position is also unknowable; a trade-through is scored as a full fill of 1 contract.

SCOPE: HIGH floor-only rungs ("temp > strike", the deployed taker's YES case), mirroring the HIGHS-ONLY
restriction of wx_earlylock_forward -- the LOW mirror can be added once the HIGH answer is known.

Usage:
    python wx_maker_study.py --report                 # tables (or the honest "blocked on data accrual" msg)
    python wx_maker_study.py --selftest               # synthetic-snapshot self-test (no network)
    python wx_maker_study.py --truth-demo [TICKER]    # demo the live settlement-truth fetch on a settled mkt
    options: --snapshots PATH  --x 1.0,2.0  --bids 94,95,96,97  --ambig 1
"""
import argparse, datetime as dt, json, math, os, ssl, sys, urllib.request
from collections import defaultdict

import kwx_runner as R          # CITY map, STATION_MARGIN/MARGIN_F -- the SAME lock geometry the taker uses

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"
IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"

SNAPSHOTS = os.path.join(HERE, "wx_book_snapshots.jsonl")   # sibling depth-logger's output (reconcile at merge)
FWD_SETTLED = os.path.join(HERE, "kwx_forward_settled.jsonl")

# --- study knobs ---
BIDS_C = (94, 95, 96, 97)   # candidate resting YES bid prices (cents) -- below the ~98c the taker pays
X_GRID = (1.0, 2.0)         # "approaching": place when the running extreme is within X degF of the strike
AMBIG_MARGIN_C = 1          # ask within this many cents ABOVE our bid (never at it) -> ambiguous fill
BASELINE_EV_C = 1.1         # deployed taker yardstick: buy ~98c post-lock, ~99.6% win -> ~+1.1c/ct net
BASELINE_PRICE_C = 98
# Maker fee: Kalshi's published fee schedule charges the quadratic trading fee to orders that TAKE liquidity;
# resting (maker) orders in the weather series carry no trading fee (maker fees exist only on designated
# index series). So headline maker EV uses fee=0; the report also prints a fee-charged sensitivity line so
# the conclusion survives even if that schedule reading is wrong or changes.
MAKER_FEE_C = 0.0


def _get(url, to=20):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=to, context=_CTX))


def _get_text(url, to=30):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "text/plain"}), timeout=to, context=_CTX).read().decode()


def _load_jsonl(path, bad_count=None):
    """Parse a jsonl file into a list of dicts (or raw JSON values). Lines that fail to parse are dropped;
    if `bad_count` is a list, its single element is incremented per unparseable line so callers that need
    to report on malformed input (e.g. load_snapshots) can see the drop instead of it being silent."""
    out = []
    if os.path.exists(path):
        for line in open(path):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                if bad_count is not None:
                    bad_count[0] += 1
    return out


def _taker_fee_c(price_c):
    """Kalshi quadratic trading fee in CENTS per contract at price_c (the sensitivity-line fee, identical
    formula to kwx_forward._kalshi_fee)."""
    p = price_c / 100.0
    return math.ceil(0.07 * p * (1 - p) * 100)


def wilson_ci(k, n, z=1.96):
    """95% Wilson score interval for a binomial proportion -- behaves sanely at the tiny n this study will
    have for weeks (a normal interval would collapse to a silly [1,1] after 3 wins)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# ---------------- ticker parsing ----------------
def parse_ticker(tk):
    """'KXHIGHDEN-26JUL18-T90' -> {series, date_iso, stype 'T'|'B', strike}. None if it doesn't parse.
    T = single-strike rung (floor-only on HIGH ladders: 'daily max > strike'); B = between (capped) rung."""
    parts = tk.split("-")
    if len(parts) != 3:
        return None
    series, datepart, strikepart = parts
    try:
        d = dt.datetime.strptime(datepart, "%y%b%d").date()   # strptime month-name match is case-insensitive
    except ValueError:
        return None
    stype = strikepart[:1]
    if stype not in ("T", "B"):
        return None
    try:
        strike = float(strikepart[1:])
    except ValueError:
        return None
    return {"series": series, "date_iso": d.isoformat(), "stype": stype, "strike": strike}


# ---------------- defensive snapshot reader ----------------
_EXTREME_ALIASES = ("running_extreme_f", "running_extreme", "running_max_f", "running_max", "extreme_f", "obs_f")


def _ladder(v):
    """Normalize a ladder to [(int price_c, int count), ...]; tolerate [p,c] lists, (p,c) tuples, or
    {'price_c':p,'count':c} dicts (the sibling's exact shape is unknown until merge). Bad levels dropped."""
    out = []
    for lvl in (v or []):
        try:
            if isinstance(lvl, dict):
                out.append((int(lvl["price_c"]), int(lvl["count"])))
            else:
                out.append((int(lvl[0]), int(lvl[1])))
        except Exception:
            continue
    return out


def load_snapshots(path):
    """Read the sibling depth-logger's jsonl into normalized snapshot dicts. Returns (snaps, stats).
    Skips (and counts) lines that violate the REQUIRED contract in the module docstring; tolerates extras."""
    snaps, stats = [], defaultdict(int)
    bad_json = [0]
    rows = _load_jsonl(path, bad_count=bad_json)
    stats["lines"] += bad_json[0]
    stats["skip_bad_json"] += bad_json[0]
    for raw in rows:
        stats["lines"] += 1
        if not isinstance(raw, dict):
            stats["skip_not_dict"] += 1
            continue
        ts_raw, tk = raw.get("ts_utc"), raw.get("ticker")
        if not ts_raw or not tk:
            stats["skip_missing_ts_or_ticker"] += 1
            continue
        try:
            ts = dt.datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except ValueError:
            stats["skip_bad_ts"] += 1
            continue
        yes_bid, yes_ask = _ladder(raw.get("yes_bid")), _ladder(raw.get("yes_ask"))
        best_ask = raw.get("best_yes_ask")
        if best_ask is None and yes_ask:
            best_ask = min(p for p, _ in yes_ask)   # derive: the contract's best_yes_ask IS min of the ladder
        try:
            best_ask = int(best_ask) if best_ask is not None else None
        except (TypeError, ValueError):
            stats["skip_bad_best_ask"] += 1
            continue
        if best_ask is None and not yes_ask and not yes_bid:
            stats["skip_no_book"] += 1              # nothing usable on either side -> not a book snapshot
            continue
        pt = parse_ticker(tk)
        # rung geometry: explicit fields win; ticker parse is the fallback (floor from a 'T' rung)
        floor = raw.get("floor", raw.get("floor_strike"))
        cap = raw.get("cap", raw.get("cap_strike"))
        if floor is None and cap is None and pt and pt["stype"] == "T":
            floor = pt["strike"]
        kind = raw.get("kind") or ("max" if pt and pt["series"].startswith("KXHIGH") else
                                   "min" if pt and pt["series"].startswith("KXLOWT") else None)
        ext = next((raw[a] for a in _EXTREME_ALIASES if raw.get(a) is not None), None)
        try:
            ext = float(ext) if ext is not None else None
        except (TypeError, ValueError):
            ext = None
        if ext is None:
            stats["no_running_extreme"] += 1        # still usable as fill evidence; counted so the gap shows
        snaps.append({
            "ts": ts, "ticker": tk, "series": pt["series"] if pt else None,
            "date": raw.get("lst_date") or raw.get("date") or (pt["date_iso"] if pt else None),
            "floor": floor, "cap": cap, "kind": kind, "ext": ext,
            "yes_bid": yes_bid, "yes_ask": yes_ask, "best_ask": best_ask,
        })
        stats["ok"] += 1
    snaps.sort(key=lambda s: (s["ticker"], s["ts"]))
    return snaps, stats


# ---------------- settlement truth ----------------
def _iem_daily_max(station, date_iso):
    """Backup truth: realized official ASOS daily max_temp_f (same source/format as wx_earlylock_forward)."""
    import io, csv
    import wx_forecast_model as M
    if station not in M.STATIONS:
        return None
    net = M.STATIONS[station][3]
    y, m, d = date_iso.split("-")
    q = (f"?network={net}&stations={M.iem_station(station)}&year1={y}&month1={int(m)}&day1={int(d)}"
         f"&year2={y}&month2={int(m)}&day2={int(d)}&var=max_temp_f&format=comma")
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


def settlement_truth(tickers, offline=False, extra=None):
    """ticker -> 'yes'/'no' (or absent when unresolvable). Priority: local settled log -> Kalshi public
    market result -> IEM daily-max backup (HIGH floor rungs only). `extra` overrides everything (selftest);
    offline=True skips all network (selftest / air-gapped runs never fetch)."""
    truth = dict(extra or {})
    local = {r["ticker"]: r["result"] for r in _load_jsonl(FWD_SETTLED)
             if r.get("ticker") and r.get("result") in ("yes", "no")}
    for tk in tickers:
        if tk in truth:
            continue
        if tk in local:
            truth[tk] = local[tk]
            continue
        if offline:
            continue
        try:
            m = _get(f"{KBASE}/markets/{tk}").get("market", {})
            if m.get("result") in ("yes", "no"):
                truth[tk] = m["result"]
                continue
        except Exception:
            pass
        pt = parse_ticker(tk)   # backup truth: official ASOS daily max vs the floor strike
        if pt and pt["stype"] == "T" and pt["series"] in R.CITY:
            station = R.CITY[pt["series"]][0]
            mx = _iem_daily_max(station, pt["date_iso"])
            if mx is not None:
                truth[tk] = "yes" if mx > pt["strike"] else "no"
    return truth


# ---------------- the simulation ----------------
def candidate_rungs(snaps):
    """Group usable snapshots by ticker: HIGH floor-only rungs with a parseable geometry. Returns
    {ticker: {'floor','station','date','snaps':[...]}} -- snaps stay time-ordered from load_snapshots."""
    by = {}
    for s in snaps:
        if s["kind"] != "max" or s["floor"] is None or s["cap"] is not None:
            continue   # HIGHS-ONLY floor rungs (the deployed YES case); B/LOW rungs are out of scope here
        e = by.setdefault(s["ticker"], {
            "floor": float(s["floor"]),
            "station": R.CITY.get(s["series"], (None,))[0] if s["series"] else None,
            "date": s["date"], "snaps": []})
        e["snaps"].append(s)
    return by


def simulate(snaps, truth, bids_c=BIDS_C, x_grid=X_GRID, ambig_c=AMBIG_MARGIN_C):
    """Replay: per (ticker, X, bid) place ONE hypothetical resting YES bid at the FIRST snapshot where the
    rung is 'approaching lock' -- running extreme within X degF of the strike but NOT yet mechanically
    locked (ext <= floor + station margin; once locked it's the taker's trade, not this study's). Then scan
    LATER same-ticker snapshots for fill evidence per the docstring's definite/ambiguous/no-fill rules.
    Returns (cells, candidates): cells[(x, bid)] = counters; candidates = per-placement records."""
    cells = {(x, b): defaultdict(int) for x in x_grid for b in bids_c}
    candidates = []
    for tk, e in candidate_rungs(snaps).items():
        floor, station = e["floor"], e["station"]
        margin = R.STATION_MARGIN.get(station, R.MARGIN_F)   # same per-station lock margin as the runner
        rows = e["snaps"]
        for x in x_grid:
            # first snapshot where the rung is approaching: within X below the strike (or above it but
            # pre-lock -- the margin zone), and the running extreme is actually known
            i0 = next((i for i, s in enumerate(rows) if s["ext"] is not None
                       and (floor - s["ext"]) <= x and s["ext"] <= floor + margin), None)
            if i0 is None:
                continue
            placed = rows[i0]
            for b in bids_c:
                c = cells[(x, b)]
                # a "resting" bid at >= the current best ask would execute immediately as a TAKER -- that's
                # the deployed strategy, not the maker experiment. Excluded and counted, not silently dropped.
                if placed["best_ask"] is not None and placed["best_ask"] <= b:
                    c["excluded_cross"] += 1
                    continue
                c["placed"] += 1
                later = [s["best_ask"] for s in rows[i0 + 1:] if s["best_ask"] is not None]
                if any(a <= b for a in later):
                    fill = "def"
                elif any(a <= b + ambig_c for a in later):
                    fill = "amb"
                else:
                    fill = "none"
                c["fill_" + fill] += 1
                res = truth.get(tk)
                if fill == "def":
                    if res == "yes":
                        c["win_def"] += 1
                    elif res == "no":
                        c["loss_def"] += 1
                    else:
                        c["unresolved_def"] += 1   # filled but truth not yet fetchable -> excluded from win%
                candidates.append({"ticker": tk, "date": e["date"], "x": x, "bid_c": b,
                                   "placed_ts": placed["ts"].isoformat(), "fill": fill, "result": res})
    return cells, candidates


def maker_ev_c(bid_c, p_win, fee_c=MAKER_FEE_C):
    """Net EV in cents/contract CONDITIONAL on fill: win pays 100-bid, loss forfeits bid, minus fee."""
    return p_win * (100 - bid_c) - (1 - p_win) * bid_c - fee_c


# ---------------- report ----------------
def _fmt_ci(k, n):
    if n == 0:
        return "   --  "
    lo, hi = wilson_ci(k, n)
    return f"{k/n:5.1%} [{lo:4.0%},{hi:4.0%}]"


def report(snap_path=SNAPSHOTS, bids_c=BIDS_C, x_grid=X_GRID, ambig_c=AMBIG_MARGIN_C,
           offline=False, truth_extra=None, out=print):
    snaps, stats = load_snapshots(snap_path)
    days = sorted({s["date"] for s in snaps if s["date"]})
    out("=== WX MAKER STUDY (resting 94-97c YES bids on rungs approaching lock) ===")
    out(f"  snapshots file : {snap_path}")
    out(f"  lines={stats['lines']}  usable={stats['ok']}  "
        f"skipped={stats['lines'] - stats['ok']}  no-running-extreme={stats['no_running_extreme']}")
    if not days:
        # the honest empty-state message: no data means NO conclusions, and says whose data it waits on
        out("\n  0 snapshot-days -- results blocked on data accrual (sibling depth-logger unit).")
        out("  Once wx_capacity_probe.py --snapshot has logged 1-2 weeks of book snapshots, rerun --report.")
        out(f"  (yardstick to beat: taker baseline {BASELINE_EV_C:+.1f}c/ct at ~{BASELINE_PRICE_C}c post-lock)")
        return
    out(f"  snapshot-days  : {len(days)}  ({days[0]} .. {days[-1]})")
    truth = settlement_truth({s["ticker"] for s in snaps}, offline=offline, extra=truth_extra)
    cells, _ = simulate(snaps, truth, bids_c=bids_c, x_grid=x_grid, ambig_c=ambig_c)
    for x in x_grid:
        out(f"\n  --- X = {x:.1f}F (place when running extreme within {x:.1f}F of strike, pre-lock) ---")
        out(f"  {'bid':>4} {'n':>4} {'cross':>5} | {'fill% (definite)':>18} {'fill% (+ambig)':>18} | "
            f"{'win%|fill':>18} {'advrs':>5} {'unres':>5} | {'EV|fill c':>9} {'EVcons c':>8} {'EV/place c':>10} {'vs taker':>8}")
        for b in bids_c:
            c = cells[(x, b)]
            n = c["placed"]
            fd, fa = c["fill_def"], c["fill_def"] + c["fill_amb"]
            resolved = c["win_def"] + c["loss_def"]
            if resolved:
                p = c["win_def"] / resolved
                p_lo, _ = wilson_ci(c["win_def"], resolved)
                ev, ev_cons = maker_ev_c(b, p), maker_ev_c(b, p_lo)   # cons = Wilson-lower-bound win prob
                ev_place = (fd / n) * ev if n else float("nan")       # per placement: fill-rate discounts EV
                tail = (f" {ev:>+8.1f} {ev_cons:>+7.1f} {ev_place:>+9.1f} "
                        f"{'BEATS' if ev_cons > BASELINE_EV_C else 'below':>8}")
            else:
                tail = f" {'--':>8} {'--':>7} {'--':>9} {'--':>8}"
            out(f"  {b:>3}c {n:>4} {c['excluded_cross']:>5} | {_fmt_ci(fd, n):>18} {_fmt_ci(fa, n):>18} | "
                f"{_fmt_ci(c['win_def'], resolved):>18} {c['loss_def']:>5} {c['unresolved_def']:>5} |" + tail)
        out(f"  (advrs = definite fills that settled NO -- the adverse-selection count; 'EVcons' uses the "
            f"Wilson lower bound of win%; taker baseline = {BASELINE_EV_C:+.1f}c/ct)")
    # fee sensitivity: if makers WERE charged the quadratic fee, the hurdle rises by ~fee at each bid
    out("\n  fee sensitivity (if maker orders were charged the taker's quadratic fee): "
        + "  ".join(f"{b}c:-{_taker_fee_c(b)}c" for b in bids_c))
    out("  CAVEATS: definite-fill is a LOWER bound (asks can flash through between sparse snapshots); "
        "queue position is unknown (a trade-through is scored as filling 1ct); ambiguous fills bracket the truth.")


# ---------------- settlement-truth live demo ----------------
def truth_demo(ticker=None):
    """Fetch settlement truth for ONE real settled Kalshi weather market via the public API -- proves the
    truth path works before any snapshot data exists. Default ticker: a settled rung from the backtest log."""
    expected = None
    if ticker is None:
        for r in json.load(open(os.path.join(HERE, "_trackA_results_raw.json"))):
            if r.get("result") in ("yes", "no"):
                ticker, expected = r["ticker"], r["result"]
                break
    print(f"settlement-truth demo: {ticker}")
    m = _get(f"{KBASE}/markets/{ticker}").get("market", {})
    print(f"  Kalshi public API : status={m.get('status')}  result={m.get('result')}")
    if expected is not None:
        agree = m.get("result") == expected
        print(f"  backtest log says : {expected}  -> {'MATCH' if agree else 'MISMATCH'}")
    pt = parse_ticker(ticker)
    if pt and pt["stype"] == "T" and pt["series"] in R.CITY:
        mx = _iem_daily_max(R.CITY[pt["series"]][0], pt["date_iso"])
        print(f"  IEM backup truth  : daily max {mx}F vs strike {pt['strike']} -> "
              f"{'yes' if mx is not None and mx > pt['strike'] else 'no/unknown'}")
    else:
        print("  IEM backup truth  : n/a for this rung type (backup covers HIGH floor rungs)")


# ---------------- synthetic self-test ----------------
def selftest():
    """Hand-built snapshots exercising every fill classification BEFORE real data exists: clean fill+win,
    fill+loss (adverse), no-fill, ambiguous fill, immediate-cross exclusion, already-locked exclusion,
    far-from-strike non-candidate, malformed/extra-field lines. Asserts exact table cells. No network."""
    import tempfile
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    def snap(ts, tk, ext, ask_c, ask_n=10):
        return {"ts_utc": ts, "ticker": tk, "running_extreme_f": ext,
                "yes_bid": [[90, 5]], "yes_ask": [[ask_c, ask_n]] if ask_c else [],
                "best_yes_ask": ask_c, "extra_field_from_sibling": "tolerated"}

    A = "KXHIGHDEN-26JUL18-T90"    # clean fill + win : ask 97 -> 93 (definite for 94-96), settles yes
    B = "KXHIGHMIA-26JUL18-T92"    # fill + LOSS      : ask 98 -> 90 (definite for all), settles no (adverse)
    C = "KXHIGHAUS-26JUL18-T100"   # no-fill          : ask 96 -> 97 -> 99 (never reaches 94/95); ext DRIFTS
                                    # AWAY from strike after row0 (.8F->.95F->1.2F) so it never re-qualifies
                                    # as "approaching" under a tighter X once placed at the X=2.0 threshold
    D = "KXHIGHCHI-26JUL18-T88"    # ambiguous        : ask 98 -> 96 (== 95+1 ambiguous; ==96 definite)
    E = "KXHIGHNY-26JUL18-T92"     # non-candidate    : running 85, strike 92 -> 7F away, outside every X
    F = "KXHIGHPHIL-26JUL18-T90"   # already locked   : running 93.5 > 90+1 margin -> taker territory, excluded
    lines = [
        snap("2026-07-18T18:00:00Z", A, 89.0, 97), snap("2026-07-18T19:00:00Z", A, 89.8, 93),
        snap("2026-07-18T18:00:00Z", B, 91.5, 98), snap("2026-07-18T19:00:00Z", B, 91.7, 90),
        snap("2026-07-18T18:00:00Z", C, 99.2, 96), snap("2026-07-18T19:00:00Z", C, 99.05, 97),
        snap("2026-07-18T20:00:00Z", C, 98.8, 99),
        snap("2026-07-18T18:00:00Z", D, 87.4, 98), snap("2026-07-18T19:00:00Z", D, 87.9, 96),
        snap("2026-07-18T18:00:00Z", E, 85.0, 97),
        snap("2026-07-18T18:00:00Z", F, 93.5, 97), snap("2026-07-18T19:00:00Z", F, 93.6, 93),
    ]
    truth = {A: "yes", B: "no", C: "yes", D: "yes", F: "yes"}
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")
        f.write("this line is not json\n")                       # reader must skip, not crash
        f.write(json.dumps({"ts_utc": "2026-07-18T18:00:00Z"}) + "\n")   # missing ticker -> skipped
        path = f.name

    snaps, stats = load_snapshots(path)
    print("reader (defensive contract):")
    check("12 usable snapshots parsed", stats["ok"] == 12, f"ok={stats['ok']}")
    check("2 malformed lines skipped, none fatal", stats["lines"] - stats["ok"] == 2)
    check("extra sibling fields tolerated", all("extra_field_from_sibling" not in s for s in snaps))

    cells, cands = simulate(snaps, truth, bids_c=(94, 95, 96, 97), x_grid=(0.75, 2.0), ambig_c=1)
    x = 2.0
    print("\nplacement geometry (X=2.0F, margin-aware, pre-lock only):")
    # A(1.0F away), B(0.5), C(0.8), D(0.6) are candidates; E is 7F away; F already locked (93.5 > 90+1)
    check("bid 94: 4 placements (A,B,C,D), E far / F locked excluded", cells[(x, 94)]["placed"] == 4,
          f"placed={cells[(x, 94)]['placed']}")
    check("no candidate row exists for locked rung F", not any(c["ticker"] == F for c in cands))
    check("bid 96: C excluded as immediate-cross (ask 96 <= bid)", cells[(x, 96)]["excluded_cross"] == 1
          and cells[(x, 96)]["placed"] == 3)
    check("bid 97: A and C excluded as immediate-cross", cells[(x, 97)]["excluded_cross"] == 2
          and cells[(x, 97)]["placed"] == 2)

    print("\nfill classification + adverse selection (X=2.0F):")
    c94 = cells[(x, 94)]
    check("bid 94: 2 definite fills (A trade-through 93, B 90)", c94["fill_def"] == 2)
    check("bid 94: 2 no-fills (C never below 96; D floor was 96)", c94["fill_none"] == 2)
    check("bid 94: fill+win=1 (A), fill+loss=1 (B adverse)", c94["win_def"] == 1 and c94["loss_def"] == 1)
    c95 = cells[(x, 95)]
    check("bid 95: D is AMBIGUOUS (ask 96 == bid+1), C stays no-fill",
          c95["fill_amb"] == 1 and c95["fill_none"] == 1 and c95["fill_def"] == 2)
    c96 = cells[(x, 96)]
    check("bid 96: D definite (ask reached 96), 3 fills / 2 wins / 1 loss",
          c96["fill_def"] == 3 and c96["win_def"] == 2 and c96["loss_def"] == 1)
    c97 = cells[(x, 97)]
    check("bid 97: B loss + D win = 2 definite fills", c97["fill_def"] == 2
          and c97["win_def"] == 1 and c97["loss_def"] == 1)

    print("\nX sensitivity (X=0.75F only admits rungs within 0.75F):")
    check("bid 94 @X=0.75: only B(0.5F) and D(0.6F) place", cells[(0.75, 94)]["placed"] == 2,
          f"placed={cells[(0.75, 94)]['placed']}")

    print("\nEV arithmetic + Wilson:")
    check("EV|fill at 95c, p=1 -> +5c", abs(maker_ev_c(95, 1.0) - 5.0) < 1e-9)
    check("EV|fill at 95c, p=0.5 -> -45c (adverse selection dominates)", abs(maker_ev_c(95, 0.5) + 45.0) < 1e-9)
    lo, hi = wilson_ci(2, 3)
    check("Wilson(2/3) is wide, not [1,1]", 0.15 < lo < 0.4 and 0.9 < hi <= 1.0, f"[{lo:.2f},{hi:.2f}]")

    print("\ntruth plumbing (offline: injected map only, no network):")
    t = settlement_truth([A, B, "KXHIGHLAX-26JUL18-T80"], offline=True, extra=truth)
    check("injected truth wins; unknown ticker stays unresolved",
          t[A] == "yes" and t[B] == "no" and "KXHIGHLAX-26JUL18-T80" not in t)

    os.unlink(path)
    print("\n" + ("ALL SELFTEST CHECKS PASSED -- fill/adverse/EV logic verified on synthetic books; "
                  "real conclusions still require accrued snapshots."
                  if not fails else f"{len(fails)} CHECK(S) FAILED: {fails}"))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description="maker-variant measurement harness (analysis only; never trades)")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--truth-demo", nargs="?", const="", metavar="TICKER")
    ap.add_argument("--snapshots", default=SNAPSHOTS)
    ap.add_argument("--x", default=",".join(str(v) for v in X_GRID), help="comma list of X degF thresholds")
    ap.add_argument("--bids", default=",".join(str(v) for v in BIDS_C), help="comma list of bid prices (c)")
    ap.add_argument("--ambig", type=int, default=AMBIG_MARGIN_C)
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if a.truth_demo is not None:
        truth_demo(a.truth_demo or None)
        return
    report(snap_path=a.snapshots, bids_c=tuple(int(v) for v in a.bids.split(",")),
           x_grid=tuple(float(v) for v in a.x.split(",")), ambig_c=a.ambig)


if __name__ == "__main__":
    main()
