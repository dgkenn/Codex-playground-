#!/usr/bin/env python3
"""kalshi_boxwide_paper.py -- FORWARD paper-track of the wide-box market-making variant found by
a 33-day PATH-SIMULATION study (scratchpad/boxwidth/{RESULTS.txt,simulate_boxwidth.py}, 1,414,602
sim rows, btc/eth/sol/xrp, day-clustered t vs W=1c reaching +33 at the wide end).

THE FINDING: rest BOTH box legs W=15c below their side of fair at a FIXED anchor time (minute 2
of the 15-min window, i.e. tau~13min to close) -- YES buy at entry_mid-W, NO buy at
(1-entry_mid)-W -- and hold both resting orders until filled or window close. If EXACTLY ONE leg
fills and the other has not completed within 60s of that first fill, DISPOSE the stranded leg via
a taker cross at (local mid at t_fill+60) -/+ 1c, paying the standard Kalshi taker fee
ceil(7*p*(1-p))c. Pooled across btc/eth/sol/xrp, the touch-fill/managed-strand curve at this
anchor is monotonically increasing in W over the SIMULATED grid W in {1,2,3,4,5,7,10}c (W=10c:
+6.58c/window, t=+48 vs W=1c, 33/33 days -- see RESULTS.txt); W=15c extrapolates ~5c past the
simulated grid's edge along that same diminishing-returns curve and was NOT itself a directly
simulated grid point in the artifacts this module was built from -- this forward paper-track is
exactly how that extrapolation gets checked against reality instead of trusted on its face.
RIDE-TO-SETTLE (no 60s disposal) is NEGATIVE at every simulated W -- the 60s disposal is not an
optional cleanup, it is THE mechanism that makes this profitable; this module implements it as a
first-class state (never as an afterthought / manual step).

VEHICLE CHOICE -- standalone paper sleeve, NOT a shadow_compare.py Strat arm (see the box-width
pre-registration note in strategies.py for the full reasoning): shadow_compare.py's Variant engine
assumes the strategy's resting quote IS the current best bid/ask (Variant.set_tob keys off `bb`/
`ba` and Variant.on_trade only ever looks up queue state at the CURRENT touch, dropping the old
entry the instant the touch moves -- "QUEUE STALENESS FIX" in that file). This mechanism instead
requires a quote resting at a FIXED price picked once at t0 and left there while the touch moves
freely for the rest of the window, filled only when the tape actually reaches that price (a
"cross" event, not a "we are quoting the touch" event) -- a structurally different fill model the
existing engine cannot express without rewriting its core queue/fill machinery. Bolting that onto
Strat/Variant as an "orthogonal, default-inert field" (the pattern px_band uses) would silently
mislabel touch-quote fills as level-crossing fills, which is worse than not having the arm at all.
So: standalone sleeve, modeled on kalshi_tailbias_paper.py's structure (GET-only public REST,
state-file ledgers, --selftest, a companion *_report.py scoring the pre-registered bar).

FILL MODEL / HONESTY NOTES:
  * Fills are detected from this module's OWN REST polling (default --interval ~1.5s, i.e. the
    "1-2s cadence" the box-width study's "touch" fill mode assumes), NOT from a continuous L2
    tape. A level can in principle be touched and vacated between two polls without being
    observed -- this is a MISS-conservative bias (never credits a fill that could not also be
    seen live), the same direction of conservatism the study's own "cross" (1-tick-through) mode
    was built to approximate, so under-crediting fills here is expected and desired, not a bug.
  * The "locked" (both-legs-filled) outcome's P&L is DETERMINISTIC at entry time: cost = L_yes +
    L_no = 1 - 2W by construction, so a completed box always nets exactly 2W regardless of fill
    order/timing -- no settlement wait needed to score it.
  * The "disposed" (managed-strand) outcome's P&L is also fully realized at dispose time (exit
    mid -/+ 1c, minus the taker fee) -- again no settlement wait needed. Kalshi settlement is only
    consulted for the rare RIDE-FORCED edge case: a leg fills so late in the window that the 60s
    dispose deadline falls after window close (only possible for a strand forming after ~t=840s;
    the anchor at minute 2 makes this rare but not impossible on a wide W that fills late).

WHAT THIS SCRIPT DOES, each polling cycle (default --duration 2520s, matching the tailbias/kxwti
paper-sleeve idiom -- one process invocation runs many cycles, see main()):
  1. Advance every open (armed/stranded) pending row against a fresh orderbook read: detect leg
     crossings, transition armed->stranded on the first fill, stranded->locked if the other leg
     completes within 60s, stranded->disposed at the 60s deadline (taker cross), or armed->neither
     if the window closes with no fill at all. Settled/expired rows are appended to
     <state_dir>/boxwide_settled.csv; anything still open is written back to
     <state_dir>/boxwide_pending.json.
  2. DISCOVER the current open KX{BTC,ETH,SOL,XRP}15M window per asset (mirrors
     kalshi_tailbias_paper.discover_window). If elapsed-since-open is in the minute-2 anchor band
     and this window has not already been armed (checked against pending), read the two-sided
     book, compute the two resting levels, and ARM a new position (one per window per asset).
  3. Append every new arm to <state_dir>/boxwide_<UTC date>.jsonl (daily diagnostic tape, same
     idiom as tailbias's/kxwti's dated jsonl).

  ============================================================================================
  PRE-REGISTERED PROMOTION BAR (set BEFORE looking at any forward-settled result; printed by
  kalshi_boxwide_report.py every run, same discipline as kalshi_tailbias_paper.py /
  strategies.py's promotion bars):
    go-live consideration for this sleeve happens ONLY once ALL of the following hold:
      >= 14 forward CALENDAR days of settled paper rows, AND
      day-clustered t >= 3.0 on realized per-window P&L, net of the disposal taker fee, vs a null
        of 0 (one mean-P&L-per-day observation per day, t computed across those day-means -- rows
         within a day share regime/volatility and must not be treated as independent draws), AND
      positive on >= 80% of the days observed, AND
      per-asset sign is CONSISTENT with the simulation on every asset counted toward the verdict
        (all 4 of btc/eth/sol/xrp were pooled-positive in the simulation) -- an asset whose
        forward-sample sign FLIPS negative must be DROPPED from the sleeve (and from the aggregate
        stat) rather than averaged away by the other assets' edge; kalshi_boxwide_report.py prints
        this per-asset check explicitly.
    NOTE on "vs av_stoikov": the operator's general standing bar for shadow_compare.py Strat arms
    is stated relative to av_stoikov (the live A/B winner in that engine, same units/mechanism as
    every other Strat). This sleeve is NOT a Strat arm (see VEHICLE CHOICE above) -- it has no
    per-fill unit comparable to av_stoikov's (different engine, different mechanism, no shared
    live collector), so there is no honest way to compute a paired same-day delta against it. This
    module instead uses the SAME null-of-zero bar kalshi_tailbias_paper.py (the other standalone
    paper sleeve in this repo) already established for exactly this situation.
    No live consideration, of any kind, before the bar clears in full.
  Score with: python kalshi_boxwide_report.py <state_dir>
  ============================================================================================

PAPER ONLY, PUBLIC READ-ONLY KALSHI REST, NO AUTH: this module sends GET requests only. It has no
API-key/private-key material, no request-signing code, and no call to any /portfolio or order
-placement endpoint anywhere in its source -- it is STRUCTURALLY INCAPABLE of touching the trading
API, unlike kalshi_trader.py. kalshi_boxwide_paper_test.py asserts this the same way
kalshi_tailbias_paper_test.py does (scanning the module's own source for auth/order markers).

Usage:
  python kalshi_boxwide_paper.py [state_dir] [--duration SECONDS] [--interval SECONDS]
    state_dir   default "gha_data/boxwide"
    --duration  default 2520 (seconds this process keeps polling before exiting)
    --interval  default 1.5 (seconds between polling cycles -- the "1-2s cadence" crossing
                detector; kept tight because it is what stands in for a continuous tape)
  python kalshi_boxwide_paper.py --selftest      # runs kalshi_boxwide_paper_test.py, no network
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://api.elections.kalshi.com/trade-api/v2"

# All 4 assets from the simulation (pooled + per-asset all positive at fixed anchor t0=120s,
# touch/managed; see RESULTS.txt) -- unlike kalshi_tailbias_paper.py, SOL is NOT excluded here.
ASSETS = ["BTC", "ETH", "SOL", "XRP"]

BOX_W = 0.15                    # dollars; half-width of each resting leg below its side of fair
ARM_LO_S, ARM_HI_S = 115.0, 145.0   # minute-2 anchor band (elapsed seconds since window open) --
#                                     a small band, not an exact instant, so imprecise poll timing
#                                     still catches "minute 2" (mirrors tailbias's tau-band idiom)
DISPOSE_DELAY_S = 60.0          # seconds after the first leg fills before disposing an uncompleted
#                                 strand -- THE essential mechanism (ride-to-settle is negative)
DISPOSE_TICK = 0.01             # dollars; disposal crosses 1c through the mid, same as the sim
FEE_MULT = 0.07                 # standard Kalshi quadratic taker-fee schedule (as elsewhere in
#                                 this repo -- fees.py/macro_paper.py/kalshi_tailbias_paper.py)
WINDOW_S = 900.0                # 15-min market length (s)
STALE_ROW_S = 1800.0            # safety net: a pending row (armed/stranded) whose book has been
#                                 unfetchable this long (well past any 15-min window + 60s dispose)
#                                 is closed out as expired_unscored rather than kept forever


# --------------------------------------------------------------------------------------------
# HTTP (GET-only, no auth headers, no order endpoints anywhere in this module)
# --------------------------------------------------------------------------------------------
def kalshi_get(path, params=None, tries=4):
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"{BASE}{path}{qs}"
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research (boxwide paper)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.load(resp)
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(1.0 * (a + 1))
    return None


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or now_utc()).isoformat(timespec="seconds")


# --------------------------------------------------------------------------------------------
# pure decision logic (no network) -- kalshi_boxwide_paper_test.py exercises these directly
# --------------------------------------------------------------------------------------------
def compute_levels(entry_mid, w=BOX_W):
    """Both resting-leg prices + the YES-bid trigger that fills the NO leg (NO is the complement
    of YES: NO_ask = 1 - YES_bid, so a NO buy at (1-entry_mid)-W fills exactly when
    YES_bid >= entry_mid+W)."""
    L_yes = round(entry_mid - w, 4)
    L_no = round((1.0 - entry_mid) - w, 4)
    trig_no = round(entry_mid + w, 4)
    return L_yes, L_no, trig_no


def levels_valid(L_yes, L_no):
    """Degenerate near the extremes (mid very close to 0 or 1, or W too wide for this mid) --
    do not arm a position with a non-positive or >=$1 resting price."""
    return 0.0 < L_yes < 1.0 and 0.0 < L_no < 1.0


def check_leg_fill(yes_bid, yes_ask, L_yes, trig_no):
    """touch-mode crossing check against the two fixed levels (see FILL MODEL note in the module
    docstring for why polling-derived detection is inherently a bit more conservative than a
    continuous tape's 'touch')."""
    yes_hit = yes_ask is not None and yes_ask <= L_yes
    no_hit = yes_bid is not None and yes_bid >= trig_no
    return yes_hit, no_hit


def taker_fee_cents(p):
    """Standard Kalshi quadratic taker-fee schedule: ceil(7*p*(1-p)) cents/contract, p in [0,1].
    Returns None on an out-of-range/missing price (caller must not silently coerce)."""
    if p is None or not (0.0 <= p <= 1.0):
        return None
    return math.ceil(FEE_MULT * p * (1.0 - p) * 100)


def lock_pnl(w=BOX_W):
    """Both legs filled: cost = L_yes + L_no = 1 - 2W by construction -> deterministic 2W profit,
    independent of fill order/timing, no settlement wait needed."""
    return round(2.0 * w, 4)


def dispose_outcome(strand_side, cost, exit_mid):
    """Managed 60s-dispose of one stranded leg: cross the book at exit_mid -/+ 1c (a taker sell of
    the resting leg's position), paying the taker fee on the exit price. Returns
    (pnl, fee_c, proceeds)."""
    if strand_side == "yes":
        proceeds = round(exit_mid - DISPOSE_TICK, 4)
        fee_c = taker_fee_cents(exit_mid)
    else:
        no_mid = round(1.0 - exit_mid, 4)
        proceeds = round(no_mid - DISPOSE_TICK, 4)
        fee_c = taker_fee_cents(no_mid)
    fee = (fee_c or 0) / 100.0
    pnl = round(proceeds - cost - fee, 4)
    return pnl, fee_c, proceeds


def ride_pnl(strand_side, cost, resolved_yes):
    """Fallback for the rare RIDE-FORCED edge case (60s dispose deadline falls after window
    close): hold the stranded leg to actual settlement instead."""
    if strand_side == "yes":
        return round(resolved_yes - cost, 4)
    return round((1.0 - resolved_yes) - cost, 4)


SETTLED_FIELDS = ["settle_ts", "asset", "ticker", "ws", "we", "entry_ts", "entry_mid", "w",
                   "L_yes", "L_no", "outcome", "strand_side", "t_fill", "dispose_mid", "fee_c",
                   "pnl", "status"]


def make_locked_row(row, now_iso_):
    return {"settle_ts": now_iso_, "asset": row["asset"], "ticker": row["ticker"], "ws": row["ws"],
            "we": row["we"], "entry_ts": row["entry_ts_iso"], "entry_mid": row["entry_mid"],
            "w": row["w"], "L_yes": row["L_yes"], "L_no": row["L_no"], "outcome": "locked",
            "strand_side": row.get("strand_side") or "", "t_fill": row.get("t_fill_iso") or "",
            "dispose_mid": "", "fee_c": 0, "pnl": lock_pnl(row["w"]), "status": "settled"}


def make_neither_row(row, now_iso_):
    return {"settle_ts": now_iso_, "asset": row["asset"], "ticker": row["ticker"], "ws": row["ws"],
            "we": row["we"], "entry_ts": row["entry_ts_iso"], "entry_mid": row["entry_mid"],
            "w": row["w"], "L_yes": row["L_yes"], "L_no": row["L_no"], "outcome": "neither",
            "strand_side": "", "t_fill": "", "dispose_mid": "", "fee_c": 0, "pnl": 0.0,
            "status": "settled"}


def make_disposed_row(row, exit_mid, now_iso_):
    pnl, fee_c, _ = dispose_outcome(row["strand_side"], row["cost"], exit_mid)
    return {"settle_ts": now_iso_, "asset": row["asset"], "ticker": row["ticker"], "ws": row["ws"],
            "we": row["we"], "entry_ts": row["entry_ts_iso"], "entry_mid": row["entry_mid"],
            "w": row["w"], "L_yes": row["L_yes"], "L_no": row["L_no"], "outcome": "disposed",
            "strand_side": row["strand_side"], "t_fill": row.get("t_fill_iso") or "",
            "dispose_mid": round(exit_mid, 4), "fee_c": fee_c, "pnl": pnl, "status": "settled"}


def make_ride_forced_row(row, resolved_yes, now_iso_):
    pnl = ride_pnl(row["strand_side"], row["cost"], resolved_yes)
    return {"settle_ts": now_iso_, "asset": row["asset"], "ticker": row["ticker"], "ws": row["ws"],
            "we": row["we"], "entry_ts": row["entry_ts_iso"], "entry_mid": row["entry_mid"],
            "w": row["w"], "L_yes": row["L_yes"], "L_no": row["L_no"], "outcome": "ride_forced",
            "strand_side": row["strand_side"], "t_fill": row.get("t_fill_iso") or "",
            "dispose_mid": "", "fee_c": 0, "pnl": pnl, "status": "settled"}


def make_expired_row(row, now_iso_):
    return {"settle_ts": now_iso_, "asset": row["asset"], "ticker": row["ticker"], "ws": row["ws"],
            "we": row["we"], "entry_ts": row["entry_ts_iso"], "entry_mid": row["entry_mid"],
            "w": row["w"], "L_yes": row["L_yes"], "L_no": row["L_no"], "outcome": "expired",
            "strand_side": row.get("strand_side") or "", "t_fill": row.get("t_fill_iso") or "",
            "dispose_mid": "", "fee_c": "", "pnl": "", "status": "expired_unscored"}


# --------------------------------------------------------------------------------------------
# network I/O: window discovery + book fetch (thin wrappers around kalshi_get; kept separate from
# the pure functions above so the strategy logic stays network-free/testable)
# --------------------------------------------------------------------------------------------
def discover_window(asset):
    """Nearest OPEN KX{asset}15M market. Mirrors kalshi_tailbias_paper.discover_window /
    kalshi_trader.discover (public, no auth)."""
    series = f"KX{asset}15M"
    d = kalshi_get("/markets", {"series_ticker": series, "status": "open", "limit": 5}) or {}
    best = None
    now = time.time()
    for m in d.get("markets") or []:
        try:
            ct = dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        if ct > now + 5 and (best is None or ct < best[1]):
            best = (m["ticker"], ct)
    if best is None:
        return None
    tk, ct = best
    return {"ticker": tk, "ws": int(ct) - 900, "we": int(ct)}


def fetch_book(ticker):
    """(yes_bid, yes_ask, no_bid, no_ask, ok) -- ya/na are DERIVED asks (mirror of the
    complementary book), matching kalshi_trader.get_book's / kalshi_tailbias_paper.fetch_book's
    convention."""
    ob = kalshi_get(f"/markets/{ticker}/orderbook", {"depth": 30})
    if ob is None:
        return None, None, None, None, False
    o = ob.get("orderbook_fp") or ob.get("orderbook") or {}
    yb_levels = o.get("yes_dollars") or []
    nb_levels = o.get("no_dollars") or []
    if not yb_levels or not nb_levels:
        return None, None, None, None, True   # one-sided/empty book, not a fetch failure
    yb = fnum(yb_levels[-1][0])
    nb = fnum(nb_levels[-1][0])
    if yb is None or nb is None:
        return None, None, None, None, True
    ya = round(1.0 - nb, 4)
    na = round(1.0 - yb, 4)
    return yb, ya, nb, na, True


def fetch_market(ticker):
    d = kalshi_get(f"/markets/{ticker}")
    if d is None:
        return {}
    return d.get("market") or {}


# --------------------------------------------------------------------------------------------
# state I/O
# --------------------------------------------------------------------------------------------
def load_pending(path):
    if not os.path.exists(path):
        return []
    try:
        return json.load(open(path))
    except Exception:
        return []


def append_settled_csv(path, rows):
    if not rows:
        return
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SETTLED_FIELDS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def append_daily_jsonl(state_dir, date_str, rows):
    if not rows:
        return
    path = os.path.join(state_dir, f"boxwide_{date_str}.jsonl")
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# --------------------------------------------------------------------------------------------
# one polling cycle: advance every open row, then discover+arm new windows
# --------------------------------------------------------------------------------------------
def _advance_row(row, now):
    """Fetch the row's book once and return (new_row_or_None, settled_row_or_None). new_row is
    None when the row has settled/expired this cycle; settled_row is None while still open."""
    now_ts = now.timestamp(); now_iso_ = iso(now)
    if now_ts - row["entry_ts"] > STALE_ROW_S:
        return None, make_expired_row(row, now_iso_)

    # NOTE: a book-fetch failure/empty-book must NOT short-circuit before the state-specific
    # logic below -- the stranded branch's RIDE-FORCED fallback and the armed branch's
    # window-close-with-no-fill close-out both need to run even when `ok` is False (the book can
    # legitimately be unfetchable right around/after a window's close).
    yb, ya, nb, na, ok = fetch_book(row["ticker"])
    have_book = ok and yb is not None and ya is not None

    if row["state"] == "armed":
        if have_book:
            yes_hit, no_hit = check_leg_fill(yb, ya, row["L_yes"], row["trig_no"])
            if yes_hit and no_hit:
                return None, make_locked_row(row, now_iso_)
            if yes_hit or no_hit:
                side = "yes" if yes_hit else "no"
                new_row = dict(row)
                new_row.update(state="stranded", strand_side=side, t_fill=now_ts,
                                t_fill_iso=now_iso_,
                                cost=row["L_yes"] if side == "yes" else row["L_no"],
                                dispose_deadline=now_ts + DISPOSE_DELAY_S)
                return new_row, None
        if now_ts >= row["we"]:
            return None, make_neither_row(row, now_iso_)
        return row, None                            # transient fetch failure -- try again next cycle

    # row["state"] == "stranded"
    if have_book:
        yes_hit, no_hit = check_leg_fill(yb, ya, row["L_yes"], row["trig_no"])
        other_hit = no_hit if row["strand_side"] == "yes" else yes_hit
        if other_hit:
            return None, make_locked_row(row, now_iso_)
    exit_mid = round((yb + ya) / 2.0, 4) if have_book else None
    if now_ts >= row["dispose_deadline"]:
        if exit_mid is not None:
            return None, make_disposed_row(row, exit_mid, now_iso_)
        if now_ts >= row["we"]:                    # book unavailable AND window has closed --
            m = fetch_market(row["ticker"])          # fall back to actual settlement (RIDE-FORCED)
            status = (m.get("status") or "").lower(); result = (m.get("result") or "").lower()
            if status == "finalized" and result in ("yes", "no"):
                resolved_yes = 1.0 if result == "yes" else 0.0
                return None, make_ride_forced_row(row, resolved_yes, now_iso_)
        return row, None                            # keep trying next cycle
    return row, None


def run_cycle(state_dir, pending):
    now = now_utc()

    settled_rows, still_pending, have = [], [], set()
    for row in pending:
        have.add(row["ticker"])
        new_row, settled = _advance_row(row, now)
        if settled is not None:
            settled_rows.append(settled)
        if new_row is not None:
            still_pending.append(new_row)

    discovered = []
    new_rows = []
    for asset in ASSETS:
        window = discover_window(asset)
        if window is None:
            discovered.append((asset, None, None))
            continue
        elapsed = now.timestamp() - window["ws"]
        discovered.append((asset, window["ticker"], elapsed))
        if window["ticker"] in have:
            continue
        if not (ARM_LO_S <= elapsed <= ARM_HI_S):
            continue
        yb, ya, nb, na, ok = fetch_book(window["ticker"])
        if not ok or yb is None or ya is None:
            continue
        entry_mid = round((yb + ya) / 2.0, 4)
        L_yes, L_no, trig_no = compute_levels(entry_mid)
        if not levels_valid(L_yes, L_no):
            continue                               # degenerate at extreme mids -- do not enter
        row = {"state": "armed", "asset": asset, "ticker": window["ticker"], "ws": window["ws"],
               "we": window["we"], "entry_ts": now.timestamp(), "entry_ts_iso": iso(now),
               "entry_mid": entry_mid, "w": BOX_W, "L_yes": L_yes, "L_no": L_no,
               "trig_no": trig_no, "strand_side": None, "t_fill": None, "t_fill_iso": None,
               "cost": None, "dispose_deadline": None}
        still_pending.append(row)
        new_rows.append(row)
        have.add(window["ticker"])

    append_settled_csv(os.path.join(state_dir, "boxwide_settled.csv"), settled_rows)
    pend_path = os.path.join(state_dir, "boxwide_pending.json")
    json.dump(still_pending, open(pend_path, "w"), indent=0)
    append_daily_jsonl(state_dir, now.date().isoformat(), new_rows)

    states = {}
    for r in still_pending:
        states[r["state"]] = states.get(r["state"], 0) + 1
    return {
        "ts": iso(now), "settled": len(settled_rows), "new_entries": len(new_rows),
        "pending_now": len(still_pending), "pending_states": states, "discovered": discovered,
    }, still_pending


# --------------------------------------------------------------------------------------------
# main: long-running poll loop (default 2520s, same idiom as kalshi_tailbias_paper.py)
# --------------------------------------------------------------------------------------------
def parse_args(argv):
    state_dir = "gha_data/boxwide"
    duration_s = 2520
    interval_s = 1.5
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--duration" and i + 1 < len(argv):
            duration_s = int(argv[i + 1]); i += 2
        elif a == "--interval" and i + 1 < len(argv):
            interval_s = float(argv[i + 1]); i += 2
        else:
            positional.append(a); i += 1
    if positional:
        state_dir = positional[0]
    return state_dir, duration_s, interval_s


def main():
    state_dir, duration_s, interval_s = parse_args(sys.argv[1:])
    os.makedirs(state_dir, exist_ok=True)
    pend_path = os.path.join(state_dir, "boxwide_pending.json")
    settled_path = os.path.join(state_dir, "boxwide_settled.csv")

    pending = load_pending(pend_path)
    start = time.time()
    cycle = 0
    while True:
        cycle += 1
        summary, pending = run_cycle(state_dir, pending)
        disc_str = " | ".join(
            f"{a}:{tk or 'none'}" + (f"(el={el:.0f}s)" if tk and el is not None else "")
            for a, tk, el in summary["discovered"]
        )
        print(f"[{summary['ts']}] cycle {cycle}: settled+{summary['settled']} "
              f"new_entries+{summary['new_entries']} pending_now={summary['pending_now']} "
              f"states={summary['pending_states']} | windows: {disc_str}")
        elapsed = time.time() - start
        if elapsed >= duration_s:
            break
        time.sleep(max(0.0, min(interval_s, duration_s - elapsed)))

    # ---------- final cumulative report ----------
    if os.path.exists(settled_path):
        n = tot = 0
        wins = 0
        outcomes = {}
        for r in csv.DictReader(open(settled_path)):
            if r.get("status") == "expired_unscored":
                continue
            n += 1
            pnl = float(r["pnl"])
            tot += pnl
            wins += pnl > 0
            outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
        if n:
            print(f"CUMULATIVE paper harvest: n={n}  mean={tot / n * 100:+.2f}c/window  "
                  f"win rate={wins / n:.3f}  outcomes={outcomes}")
        else:
            print("no settled paper windows yet (edge accrues as windows resolve)")
    else:
        print("no settled paper windows yet (edge accrues as windows resolve)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        import kalshi_boxwide_paper_test
        sys.exit(kalshi_boxwide_paper_test.run())
    main()
