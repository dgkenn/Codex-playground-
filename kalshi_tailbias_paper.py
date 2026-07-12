#!/usr/bin/env python3
"""kalshi_tailbias_paper.py -- FORWARD paper-track of the favorite-longshot bias in Kalshi's
15-min crypto binaries (KXBTC15M/KXETH15M/KXXRP15M).

THE EDGE (33-day calibration study, 11,219 settled windows, per-asset breakdown in the study
writeup): at tau ~9 minutes to expiry, the cheaper ("tail") side priced 7-15c settles
in-the-money materially LESS often than its price implies (e.g. the 10-15c bin: implied 12.5%
vs realized 9.6%, day-clustered t=-3.11, sign-stable across all 5 calibration weeks). SELLING
the tail -- equivalently BUYING the favorite -- nets approx +1.2c/contract as a taker after fees,
approx +2.2c/contract as a hypothetical maker. Holds on BTC/ETH/XRP; SOL was flat-to-opposite in
the calibration study and is EXCLUDED here (ASSETS below has no "SOL" -- do not add it back
without a fresh calibration).

WHAT THIS SCRIPT DOES, each polling cycle (default --duration 2520s, one process invocation runs
many cycles -- see main()):
  1. SETTLE matured pendings: GET /markets/{ticker} for every open paper position and check
     status=="finalized" (Kalshi's REAL per-market status field for a resolved market -- see
     kalshi_longshot_paper.py's BUG-1 fix; that lesson is applied here from the start, not
     retrofitted). Realized P&L for BOTH execution variants (taker/maker) is appended to
     <state_dir>/tailbias_settled.csv. A pending position unresolved >STALE_PENDING_DAYS days
     (2 -- these are 15-MINUTE markets, they finalize fast; anything still unresolved after 2
     days is an API anomaly, not a real open position) gets an explicit status=expired_unscored
     row instead of being silently dropped.
  2. DISCOVER the current open KXBTC15M/KXETH15M/KXXRP15M window per asset (nearest close_time,
     mirrors kalshi_trader.discover). If tau (seconds to close) is in [8.0, 10.0] minutes and this
     window's ticker has not already been entered (checked against the pending state -- at most
     ONE entry per window per asset), read the two-sided book and evaluate the entry rule
     (evaluate_entry(), pure/network-free, unit tested in kalshi_tailbias_paper_test.py):
       - identify the TAIL side = whichever of YES/NO has the cheaper ask (identify_tail_side());
         a tied ask is ambiguous and is NOT entered.
       - if tail ask in [0.07, 0.15] and both sides of the book are present (two-sided market),
         record a PAPER position: BUY THE FAVORITE (the other side). Both execution variants are
         logged in the SAME row: taker_px = favorite ask (what a market/IOC order pays right now);
         maker_px = favorite ask - 0.01 (a HYPOTHETICAL join-the-queue price -- see FILL MODEL).
  3. Append every new position to <state_dir>/tailbias_pending.json (persists across runs/cycles)
     AND to <state_dir>/tailbias_<UTC date>.jsonl (one growing append-only diagnostic line per
     accepted entry, date-partitioned -- mirrors macro_paper.py/kxwti_paper.py's daily-tape idiom;
     tailbias_pending.json + tailbias_settled.csv mirror kalshi_longshot_paper.py's state-file
     naming/layout).

FILL MODEL / HONESTY NOTES:
  * taker variant: assumes an immediate fill AT THE OBSERVED ASK, i.e. what an IOC/market order
    would pay in a two-sided, non-stale book at the moment of the read. This is the variant this
    module's PRE-REGISTERED PROMOTION BAR (below) actually governs, precisely because it needs no
    fill-probability assumption.
  * maker variant: HYPOTHETICAL. There is NO queue model here -- resting a real maker order 1c
    inside the favorite ask might not fill at all, might fill at a worse effective price after
    adverse selection, or might fill better via price improvement. The maker_px/pnl_maker columns
    are logged for visibility and for eventually informing a maker-style execution INSIDE the
    live trader (kalshi_trader.py), which already prices/gates/sizes maker quotes with a real
    fill/inventory model. They must NEVER be read as "the strategy nets +2.2c/contract" on their
    own -- see the promotion bar below.

  ============================================================================================
  PRE-REGISTERED PROMOTION BAR (set BEFORE looking at any forward-settled result; printed by
  kalshi_tailbias_report.py every run so it can't drift -- same discipline as strategies.py's
  promotion bars and edge_verdicts.py's default gate):
    go-live consideration for this sleeve happens ONLY once ALL of the following hold:
      >= 14 forward CALENDAR days of settled paper rows, AND
      day-clustered t >= 3.0 on the TAKER variant, net of fees, vs a null of 0
        (one mean-P&L-per-day observation per day, t computed across those day-means -- rows
         within a day share regime/volatility and must not be treated as independent draws), AND
      positive on >= 80% of the days observed (TAKER variant), AND
      per-asset sign is CONSISTENT with the calibration study on every asset counted toward the
        verdict -- an asset whose forward-sample sign FLIPS negative must be DROPPED from the
        sleeve (and from the aggregate stat) rather than averaged away by the other assets'
        edge; kalshi_tailbias_report.py prints this per-asset check explicitly.
    The MAKER variant's fills are HYPOTHETICAL (no queue model, see FILL MODEL above): even a
    forward maker-variant PASS on this bar can only justify piloting MAKER-STYLE execution of
    this edge INSIDE the existing live trader (kalshi_trader.py, which has a real fill/inventory
    model) -- it can NEVER by itself justify a standalone maker deployment of this module, because
    this module cannot observe whether its hypothetical resting quote would truly have been
    lifted first.
    No live consideration, of any kind, before the TAKER bar clears.
  Score with: python kalshi_tailbias_report.py <state_dir>
  ============================================================================================

PAPER ONLY, PUBLIC READ-ONLY KALSHI REST, NO AUTH: this module sends GET requests only. It has no
API-key/private-key material, no request-signing code, and no call to any /portfolio or order
-placement endpoint anywhere in its source -- it is STRUCTURALLY INCAPABLE of touching the trading
API, unlike kalshi_trader.py. kalshi_tailbias_paper_test.py asserts this by scanning the module's
own source for auth/order-placement markers (same technique kalshi_longshot_paper_test.py uses).

Usage:
  python kalshi_tailbias_paper.py [state_dir] [--duration SECONDS] [--interval SECONDS]
    state_dir   default "gha_data/tailbias"
    --duration  default 2520 (seconds this process keeps polling before exiting -- one long-lived
                run per GH Actions invocation, same idiom as sidecar_feeds.py)
    --interval  default 20 (seconds between polling cycles)
  python kalshi_tailbias_paper.py --selftest      # runs kalshi_tailbias_paper_test.py, no network
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

# Assets validated by the calibration study. SOL is deliberately excluded (flat-to-opposite sign
# in the study) -- do not add it back without a fresh calibration confirming the sign.
ASSETS = ["BTC", "ETH", "XRP"]

TAIL_LO, TAIL_HI = 0.07, 0.15          # tail-ask entry band (dollars/probability, 0-1 scale)
TAU_LO_MIN, TAU_HI_MIN = 8.0, 10.0     # entry window, minutes-to-close
TAU_LO_S = TAU_LO_MIN * 60.0
TAU_HI_S = TAU_HI_MIN * 60.0
FEE_MULT = 0.07                         # standard Kalshi quadratic taker-fee schedule (as elsewhere
                                         # in this repo -- macro_paper.py/kalshi_macro_snap.py)
MAKER_TAKE = 0.01                       # hypothetical maker improvement off the taker ask
STALE_PENDING_DAYS = 2                  # 15-min markets finalize fast; unresolved >2d = API anomaly


# --------------------------------------------------------------------------------------------
# HTTP (GET-only, no auth headers, no order endpoints anywhere in this module -- see docstring)
# --------------------------------------------------------------------------------------------
def kalshi_get(path, params=None, tries=4):
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"{BASE}{path}{qs}"
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research (tailbias paper)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.load(resp)
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(1.2 * (a + 1))
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
# pure decision logic (no network) -- kalshi_tailbias_paper_test.py exercises these directly
# --------------------------------------------------------------------------------------------
def identify_tail_side(yes_ask, no_ask):
    """Return 'yes' or 'no' for whichever side has the CHEAPER ask (the tail), or None if either
    price is missing OR the two asks are tied. A tie means neither side is identifiably cheaper --
    we do not guess a favorite in that case, we just skip the window this cycle."""
    if yes_ask is None or no_ask is None:
        return None
    if yes_ask < no_ask:
        return "yes"
    if no_ask < yes_ask:
        return "no"
    return None


def in_tau_band(tau_s, lo_s=TAU_LO_S, hi_s=TAU_HI_S):
    return tau_s is not None and lo_s <= tau_s <= hi_s


def in_tail_band(tail_ask, lo=TAIL_LO, hi=TAIL_HI):
    return tail_ask is not None and lo <= tail_ask <= hi


def taker_fee_cents(entry_price):
    """Standard Kalshi quadratic taker-fee schedule: ceil(7 * p * (1-p)) cents/contract, entry_price
    in [0,1]. Returns None on an out-of-range/missing price (caller must not silently coerce)."""
    if entry_price is None or not (0.0 <= entry_price <= 1.0):
        return None
    return math.ceil(FEE_MULT * entry_price * (1.0 - entry_price) * 100)


def evaluate_entry(yes_bid, yes_ask, no_bid, no_ask, tau_s,
                    yes_bid_qty=None, no_bid_qty=None):
    """Pure entry-rule evaluation given one book snapshot + tau (seconds to window close). Returns
    None if the tail-bias entry rule does NOT fire this cycle, else a dict describing the paper
    trade (BUY THE FAVORITE) with both execution-price variants. Side-effect-free and
    network-free by construction -- this is the whole strategy logic, kept separate from I/O so it
    can be unit tested without the network (see kalshi_tailbias_paper_test.py).

    Book convention (matches kalshi_trader.get_book / kxwti_paper.book): yes_bid/no_bid are the
    two RAW touches off the complementary order book; yes_ask/no_ask are the (already-derived)
    asks passed in -- yes_ask = 1 - best_no_bid, no_ask = 1 - best_yes_bid.
    """
    if yes_bid is None or yes_ask is None or no_bid is None or no_ask is None:
        return None                      # two-sided book required
    if not (0 < yes_bid < yes_ask < 1) or not (0 < no_bid < no_ask < 1):
        return None
    if not in_tau_band(tau_s):
        return None
    tail = identify_tail_side(yes_ask, no_ask)
    if tail is None:
        return None                      # tied/ambiguous -- do not enter
    tail_ask = yes_ask if tail == "yes" else no_ask
    if not in_tail_band(tail_ask):
        return None
    fav = "no" if tail == "yes" else "yes"
    fav_bid = no_bid if fav == "no" else yes_bid
    fav_ask = no_ask if fav == "no" else yes_ask
    # size at the touch we'd cross as a taker buying the favorite: the OPPOSITE side's resting
    # bid depth is what constitutes the favorite's implied ask (favorite ask = 1 - opposite bid).
    size_at_touch = (no_bid_qty if fav == "yes" else yes_bid_qty)
    taker_px = round(fav_ask, 4)
    maker_px = round(fav_ask - MAKER_TAKE, 4)
    fee_c = taker_fee_cents(taker_px)
    return {
        "tail_side": tail, "tail_px": round(tail_ask, 4),
        "fav_side": fav, "fav_bid": round(fav_bid, 4), "fav_ask": round(fav_ask, 4),
        "spread": round(fav_ask - fav_bid, 4),
        "size_at_touch": size_at_touch,
        "taker_px": taker_px, "taker_fee_c": fee_c, "maker_px": maker_px,
    }


def classify_settlement(p, m, now, stale_days=STALE_PENDING_DAYS):
    """Decide the fate of one pending position p given its current market state m (dict from
    GET /markets/{ticker}, or {} if the ticker 404'd/vanished). Mirrors
    kalshi_longshot_paper.classify_settlement's fixed status check (status=="finalized" is
    Kalshi's real per-market resolved-status value; "settled" is only a query-FILTER value and
    never appears as a returned market's status field -- applying that lesson here from the start).
    Returns ("settle", row) | ("pending", None) | ("expired", row)."""
    status = (m.get("status") or "").lower()
    result = (m.get("result") or "").lower()
    if status == "finalized" and result in ("yes", "no"):
        settle_yes = 1.0 if result == "yes" else 0.0
        settle_fav = settle_yes if p["fav_side"] == "yes" else (1.0 - settle_yes)
        taker_fee = (p.get("taker_fee_c") or 0) / 100.0
        pnl_taker = round(settle_fav - p["taker_px"] - taker_fee, 4)
        # maker fee = 0 on KX*15M crypto markets (confirmed live, kalshi_trader.py: "Kalshi fills
        # report fee in fee_cost (=0 on KXBTC15M maker)") -- hypothetical fill, see module docstring.
        pnl_maker = round(settle_fav - p["maker_px"], 4)
        return "settle", {
            "settle_ts": iso(now), "snap_ts": p["ts"], "asset": p["asset"], "ticker": p["ticker"],
            "ws": p.get("ws"), "we": p.get("we"), "tau_s_at_entry": p.get("tau_s_at_entry"),
            "tail_side": p["tail_side"], "tail_px": p["tail_px"], "fav_side": p["fav_side"],
            "fav_bid": p["fav_bid"], "fav_ask": p["fav_ask"], "spread": p["spread"],
            "size_at_touch": p.get("size_at_touch"),
            "taker_px": p["taker_px"], "taker_fee_c": p["taker_fee_c"], "maker_px": p["maker_px"],
            "result": result, "settle_fav": settle_fav,
            "pnl_taker": pnl_taker, "pnl_maker": pnl_maker, "status": "settled",
        }
    age_days = (now - dt.datetime.fromisoformat(p["ts"])).days
    if age_days <= stale_days:
        return "pending", None
    return "expired", {
        "settle_ts": iso(now), "snap_ts": p["ts"], "asset": p["asset"], "ticker": p["ticker"],
        "ws": p.get("ws"), "we": p.get("we"), "tau_s_at_entry": p.get("tau_s_at_entry"),
        "tail_side": p["tail_side"], "tail_px": p["tail_px"], "fav_side": p["fav_side"],
        "fav_bid": p["fav_bid"], "fav_ask": p["fav_ask"], "spread": p["spread"],
        "size_at_touch": p.get("size_at_touch"),
        "taker_px": p["taker_px"], "taker_fee_c": p["taker_fee_c"], "maker_px": p["maker_px"],
        "result": result or "unresolved", "settle_fav": "",
        "pnl_taker": "", "pnl_maker": "", "status": "expired_unscored",
    }


SETTLED_FIELDS = ["settle_ts", "snap_ts", "asset", "ticker", "ws", "we", "tau_s_at_entry",
                   "tail_side", "tail_px", "fav_side", "fav_bid", "fav_ask", "spread",
                   "size_at_touch", "taker_px", "taker_fee_c", "maker_px", "result", "settle_fav",
                   "pnl_taker", "pnl_maker", "status"]


# --------------------------------------------------------------------------------------------
# network I/O: window discovery + book fetch (thin wrappers around kalshi_get; kept separate from
# evaluate_entry so the strategy logic above stays network-free/testable)
# --------------------------------------------------------------------------------------------
def discover_window(asset):
    """Nearest OPEN KX{asset}15M market. Mirrors kalshi_trader.discover (public, no auth)."""
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
    """(yes_bid, yes_bid_qty, yes_ask, no_bid, no_bid_qty, no_ask, ok). ya/na are DERIVED asks
    (mirror of the complementary book), matching kalshi_trader.get_book's convention."""
    ob = kalshi_get(f"/markets/{ticker}/orderbook", {"depth": 30})
    if ob is None:
        return None, None, None, None, None, None, False
    o = ob.get("orderbook_fp") or ob.get("orderbook") or {}
    yb_levels = o.get("yes_dollars") or []
    nb_levels = o.get("no_dollars") or []
    if not yb_levels or not nb_levels:
        return None, None, None, None, None, None, True   # one-sided/empty book, not a fetch failure
    yb, ybq = fnum(yb_levels[-1][0]), fnum(yb_levels[-1][1])
    nb, nbq = fnum(nb_levels[-1][0]), fnum(nb_levels[-1][1])
    if yb is None or nb is None:
        return None, None, None, None, None, None, True
    ya = round(1.0 - nb, 4)
    na = round(1.0 - yb, 4)
    return yb, ybq, ya, nb, nbq, na, True


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
    path = os.path.join(state_dir, f"tailbias_{date_str}.jsonl")
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# --------------------------------------------------------------------------------------------
# one polling cycle (settle matured pendings, then look for new entries)
# --------------------------------------------------------------------------------------------
def run_cycle(state_dir, pending):
    now = now_utc()
    nowiso = iso(now)

    # ---------- 1. SETTLE matured pendings ----------
    settled_rows, expired_rows, still_pending = [], [], []
    for p in pending:
        m = fetch_market(p["ticker"])
        action, row = classify_settlement(p, m, now)
        if action == "pending":
            still_pending.append(p)
        elif action == "settle":
            settled_rows.append(row)
        else:
            expired_rows.append(row)
    append_settled_csv(os.path.join(state_dir, "tailbias_settled.csv"), settled_rows + expired_rows)

    # ---------- 2. discover current windows + evaluate the entry rule ----------
    have = {p["ticker"] for p in still_pending}
    new_rows = []
    discovered = []
    for asset in ASSETS:
        window = discover_window(asset)
        if window is None:
            discovered.append((asset, None, None))
            continue
        tau_s = window["we"] - now.timestamp()
        discovered.append((asset, window["ticker"], tau_s))
        if window["ticker"] in have:
            continue                       # already entered this window (max one/window/asset)
        if not in_tau_band(tau_s):
            continue                       # cheap check before hitting the book endpoint
        yb, ybq, ya, nb, nbq, na, ok = fetch_book(window["ticker"])
        if not ok:
            continue
        decision = evaluate_entry(yb, ya, nb, na, tau_s, yes_bid_qty=ybq, no_bid_qty=nbq)
        if decision is None:
            continue
        row = dict(decision)
        row.update({"ts": nowiso, "asset": asset, "ticker": window["ticker"],
                     "ws": window["ws"], "we": window["we"], "tau_s_at_entry": round(tau_s, 1)})
        still_pending.append(row)
        new_rows.append(row)
        have.add(window["ticker"])

    pend_path = os.path.join(state_dir, "tailbias_pending.json")
    json.dump(still_pending, open(pend_path, "w"), indent=0)
    append_daily_jsonl(state_dir, now.date().isoformat(), new_rows)

    return {
        "ts": nowiso, "settled": len(settled_rows), "expired": len(expired_rows),
        "new_entries": len(new_rows), "pending_now": len(still_pending),
        "discovered": discovered,
    }, still_pending


# --------------------------------------------------------------------------------------------
# main: long-running poll loop (default 2520s, same idiom as sidecar_feeds.py)
# --------------------------------------------------------------------------------------------
def parse_args(argv):
    state_dir = "gha_data/tailbias"
    duration_s = 2520
    interval_s = 20
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--duration" and i + 1 < len(argv):
            duration_s = int(argv[i + 1]); i += 2
        elif a == "--interval" and i + 1 < len(argv):
            interval_s = int(argv[i + 1]); i += 2
        else:
            positional.append(a); i += 1
    if positional:
        state_dir = positional[0]
    return state_dir, duration_s, interval_s


def main():
    state_dir, duration_s, interval_s = parse_args(sys.argv[1:])
    os.makedirs(state_dir, exist_ok=True)
    pend_path = os.path.join(state_dir, "tailbias_pending.json")
    settled_path = os.path.join(state_dir, "tailbias_settled.csv")

    pending = load_pending(pend_path)
    start = time.time()
    cycle = 0
    while True:
        cycle += 1
        summary, pending = run_cycle(state_dir, pending)
        disc_str = " | ".join(
            f"{a}:{tk or 'none'}"
            + (f"(tau={ts:.0f}s)" if tk and ts is not None else "")
            for a, tk, ts in summary["discovered"]
        )
        print(f"[{summary['ts']}] cycle {cycle}: settled+{summary['settled']} "
              f"expired+{summary['expired']} new_entries+{summary['new_entries']} "
              f"pending_now={summary['pending_now']} | windows: {disc_str}")
        elapsed = time.time() - start
        if elapsed >= duration_s:
            break
        time.sleep(max(0.0, min(interval_s, duration_s - elapsed)))

    # ---------- final cumulative report ----------
    if os.path.exists(settled_path):
        n = tot_t = tot_m = 0
        wins = 0
        for r in csv.DictReader(open(settled_path)):
            if r.get("status") == "expired_unscored":
                continue
            n += 1
            tot_t += float(r["pnl_taker"])
            tot_m += float(r["pnl_maker"])
            wins += float(r["pnl_taker"]) > 0
        if n:
            print(f"CUMULATIVE paper harvest: n={n}  taker mean={tot_t / n * 100:+.2f}c/contract  "
                  f"maker(hypothetical) mean={tot_m / n * 100:+.2f}c/contract  "
                  f"taker win rate={wins / n:.3f}")
        else:
            print("no settled paper positions yet (edge accrues as windows resolve)")
    else:
        print("no settled paper positions yet (edge accrues as windows resolve)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        import kalshi_tailbias_paper_test
        sys.exit(kalshi_tailbias_paper_test.run())
    main()
