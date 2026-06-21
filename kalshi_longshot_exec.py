#!/usr/bin/env python3
"""
kalshi_longshot_exec.py

EXECUTION OPTIMIZER for the soft-market longshot-MAKER harvest.

Strategy under study (from KALSHI_MAKER_VERDICT.md):
    Be the maker who SELLS overpriced YES longshots on soft, zero-maker-fee
    Kalshi categories. Equivalently: rest a NO-BUY at/near the touch. When a
    recreational taker LIFTS the YES ask (taker_side == "yes"), our resting
    YES-sell offer is hit -> we go SHORT YES (== LONG NO). Realized maker edge
    to settlement on the longshot band is the known +0.97c/contract baseline.

This script does NOT re-derive that edge. It optimizes HOW and WHEN we quote:

  (1) ENTRY TIMING -- bucket each settled longshot market's life into
      early/mid/late thirds; for each third measure (a) fillable YES-lift flow
      and (b) the realized maker-NO edge of quoting then. Tests whether the
      settlement-loaded late flow really pays worse and whether an early/mid
      sweet spot has BOTH edge and fills.

  (2) QUOTE PLACEMENT -- AT the touch (rest YES-sell at yes_ask, i.e. NO-buy at
      no_bid) vs INSIDE (improve: sell YES 1c cheaper to win queue) vs JOIN
      DEEPER (sell YES 1c higher, more premium, fewer fills). Model the
      premium-vs-fill tradeoff from candle bid/ask + which trades print at/through
      each level.

  (3) HOLD vs EARLY-EXIT -- after the maker is short YES, does holding to
      settlement beat buying the YES back (closing the short) when the longshot
      mean-reverts/decays mid-life? Compare realized P&L of HOLD-TO-SETTLE vs
      EXIT-when-YES-mid-drops-to-X (take-profit) and EXIT-on-adverse-move
      (stop) using the per-minute candle path after each fill.

  (4) RE-QUOTE CADENCE -- with a thin, bursty book, how stale can a quote get?
      Measure how the touch moves minute-to-minute and what fraction of fillable
      flow you'd miss at refresh intervals of 1 / 5 / 15 / 60 min.

Realism / fill model
--------------------
A taker YES-lift at price p_trade fills a resting YES-sell offer placed at level
L (in YES cents) iff p_trade >= L (taker willing to pay at least our offer).
We additionally apply a QUEUE-CAPTURE haircut q (we are not alone at the touch):
expected filled contracts at a print = count * q, with q depending on placement:
  - INSIDE (improve, sell 1c cheaper): q_improve  (front of queue, best capture)
  - AT touch:                          q_touch
  - JOIN deeper (1c higher):           q_join      (only fills if flow reaches us)
These q's are reported as a sensitivity band; the *ranking* of policies is robust
to the exact q because every policy is haircut by the same flow.

Output: kalshi_longshot_exec_results.{txt,json}; the .md is written by hand from these.

Public Kalshi API, no auth. Rate-limited: ~0.4s between calls, exp backoff on 429.
"""

import json
import time
import sys
import math
import argparse
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
# Soft, zero-maker-fee categories (per KALSHI_MAKER_RANK.md). Climate is the most
# plentiful tradeable soft series; Politics/Entertainment/Science add breadth.
CATEGORIES = ["Climate and Weather", "Politics", "Entertainment", "Science and Technology"]

MIN_VOLUME_FP = 300.0
MAX_SERIES_PER_CAT = 25
MAX_MARKETS_PER_SERIES = 40
MAX_MARKETS_TOTAL = 500
REQUEST_PAUSE = 0.40            # >= 0.4s between calls per the rate-limit mandate

# Longshot YES band (mid 0.02-0.20). We assign band by the trade's yes price.
LONGSHOT_LO = 0.02
LONGSHOT_HI = 0.20

# Queue-capture haircuts by placement (expected share of a taker print we win).
Q_IMPROVE = 0.50   # we improved the offer -> front of queue
Q_TOUCH   = 0.25   # we sit at the touch with others
Q_JOIN    = 0.12   # we rest 1c worse (for the taker) -> only deep sweeps reach us

# Take-profit / stop levels for the hold-vs-exit study (in YES mid terms).
# After we are short YES at fill price f, "profit" = YES mid falls (we can buy back
# cheaper). TP_FRAC: close when YES mid has fallen to TP_FRAC * f. STOP_MULT: close
# (cut loss) when YES mid has risen to STOP_MULT * f.
TP_FRACS = [0.5, 0.25]
STOP_MULTS = [2.0, 3.0]

FEE_RATE = 0.0   # soft categories are ZERO maker fee (KALSHI_MAKER_RANK.md). Set
                 # >0 to stress-test; baseline doc charged 0.07 conservatively.


def http_get(path, params=None, retries=5):
    url = BASE + path
    if params:
        url = url + "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None and v != ""})
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json",
                              "User-Agent": "longshot-exec-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(0.5 * (2 ** i))
                continue
            return None
        except Exception:
            time.sleep(0.5 * (2 ** i))
    return None


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def fnum(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


# ---------------------------------------------------------------- discovery
def list_series(category):
    out, cursor = [], ""
    while True:
        d = http_get("/series", {"category": category, "limit": 100, "cursor": cursor})
        if not d:
            break
        out.extend(d.get("series", []))
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= 300:
            break
        time.sleep(REQUEST_PAUSE)
    return out


def list_settled_markets(series_ticker):
    out, cursor = [], ""
    while True:
        d = http_get("/markets", {"series_ticker": series_ticker, "status": "settled",
                                  "limit": 100, "cursor": cursor})
        if not d:
            break
        out.extend(d.get("markets", []))
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= MAX_MARKETS_PER_SERIES:
            break
        time.sleep(REQUEST_PAUSE)
    return out[:MAX_MARKETS_PER_SERIES]


def get_trades(ticker):
    out, cursor = [], ""
    for _ in range(8):  # up to 8k trades
        d = http_get("/markets/trades", {"ticker": ticker, "limit": 1000, "cursor": cursor})
        if not d:
            break
        ts = d.get("trades", [])
        out.extend(ts)
        cursor = d.get("cursor") or ""
        if not cursor or not ts:
            break
        time.sleep(REQUEST_PAUSE)
    return out


def get_candles(series_ticker, ticker, start_ts, end_ts):
    d = http_get(f"/series/{series_ticker}/markets/{ticker}/candlesticks",
                 {"start_ts": int(start_ts), "end_ts": int(end_ts), "period_interval": 60})
    if not d:
        return []
    return d.get("candlesticks", [])


def candle_mid(c):
    yb = fnum((c.get("yes_bid") or {}).get("close_dollars"))
    ya = fnum((c.get("yes_ask") or {}).get("close_dollars"))
    if yb is not None and ya is not None and 0 <= yb <= 1 and 0 < ya <= 1 and ya >= yb:
        # for a deep longshot the YES bid is frequently 0; use ask-anchored proxy
        if yb == 0.0:
            return ya / 2.0 if ya > 0 else None
        return (yb + ya) / 2.0
    pc = fnum((c.get("price") or {}).get("close_dollars"))
    return pc


def fee(p):
    return FEE_RATE * p * (1.0 - p)


# ---------------------------------------------------------------- accumulator
class Acc:
    def __init__(self):
        self.n = 0
        self.contracts = 0.0
        self.sum_w = 0.0
        self.sum_t = 0.0
        self.sumsq_t = 0.0

    def add(self, pnl, contracts):
        self.n += 1
        self.contracts += contracts
        self.sum_w += contracts * pnl
        self.sum_t += pnl
        self.sumsq_t += pnl * pnl

    def vw(self):
        return self.sum_w / self.contracts if self.contracts > 0 else float("nan")

    def tw(self):
        return self.sum_t / self.n if self.n else float("nan")

    def se(self):
        if self.n < 2:
            return float("nan")
        m = self.tw()
        var = (self.sumsq_t - self.n * m * m) / (self.n - 1)
        return math.sqrt(max(var, 0.0) / self.n)


THIRDS = ["early", "mid", "late"]
PLACEMENTS = ["improve", "touch", "join"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-markets", type=int, default=MAX_MARKETS_TOTAL)
    ap.add_argument("--categories", nargs="*", default=CATEGORIES)
    args = ap.parse_args()

    # (1) entry timing: maker-NO realized P&L to settle, by life-third
    third_pnl = {t: Acc() for t in THIRDS}
    # fillable YES-lift flow (contracts) by third (the flow we could ever sell into)
    third_flow = {t: 0.0 for t in THIRDS}
    third_trades = {t: 0 for t in THIRDS}

    # (2) placement: realized maker-NO P&L by placement level, with queue haircut.
    place_pnl = {pl: Acc() for pl in PLACEMENTS}
    place_flow = {pl: 0.0 for pl in PLACEMENTS}     # expected filled contracts
    # (2b) placement x third interaction
    place_third_pnl = {(pl, t): Acc() for pl in PLACEMENTS for t in THIRDS}

    # (3) hold vs exit: per fill, hold-to-settle vs TP/stop exits on candle path.
    hold_acc = Acc()
    tp_acc = {f: Acc() for f in TP_FRACS}
    stop_acc = {m: Acc() for m in STOP_MULTS}
    combo_acc = Acc()   # TP=0.5 + STOP=3.0 combined manager (illustrative best)

    # (4) re-quote cadence: of all fillable flow, fraction reachable at refresh R.
    REFRESHES = [1, 5, 15, 60]   # minutes
    cadence_capt = {r: 0.0 for r in REFRESHES}
    cadence_total = 0.0
    # touch movement: |yes_ask change| minute over minute (cents)
    touch_moves = []

    markets_done = 0
    markets_with_candles = 0
    longshot_markets = 0
    series_seen = set()
    by_cat = defaultdict(int)

    for cat in args.categories:
        sys.stderr.write(f"\n=== {cat} ===\n")
        series = list_series(cat)
        sys.stderr.write(f"  series: {len(series)}\n")
        scanned = 0
        for s in series:
            if markets_done >= args.max_markets:
                break
            stk = s.get("ticker")
            if not stk or stk in series_seen:
                continue
            series_seen.add(stk)
            scanned += 1
            if scanned > MAX_SERIES_PER_CAT:
                break
            markets = list_settled_markets(stk)
            for m in markets:
                if markets_done >= args.max_markets:
                    break
                if m.get("mve_collection_ticker"):
                    continue
                if m.get("market_type") not in (None, "binary"):
                    continue
                if fnum(m.get("volume_fp"), 0.0) < MIN_VOLUME_FP:
                    continue
                result = m.get("result")
                if result not in ("yes", "no"):
                    continue
                settle = 1.0 if result == "yes" else 0.0
                tk = m.get("ticker")
                ot = parse_ts(m.get("open_time"))
                ct = parse_ts(m.get("close_time"))
                if not (ot and ct and ct > ot):
                    continue

                trades = get_trades(tk)
                if not trades:
                    continue
                markets_done += 1
                by_cat[cat] += 1

                candles = get_candles(stk, tk, ot - 120, ct + 120)
                cseries = []
                for c in candles:
                    ept = c.get("end_period_ts")
                    mid = candle_mid(c)
                    ya = fnum((c.get("yes_ask") or {}).get("close_dollars"))
                    if ept is not None:
                        cseries.append((float(ept), mid, ya))
                cseries.sort()
                if cseries:
                    markets_with_candles += 1
                    # touch movement series (yes_ask minute deltas, in cents)
                    prev_ya = None
                    for _, _, ya in cseries:
                        if ya is not None and prev_ya is not None:
                            touch_moves.append(abs(ya - prev_ya) * 100.0)
                        if ya is not None:
                            prev_ya = ya

                def mid_after(t_epoch, minutes):
                    target = t_epoch + minutes * 60
                    for ept, mid, _ in cseries:
                        if ept >= target and mid is not None:
                            if ept - target <= minutes * 60 * 3 + 120:
                                return mid
                            return None
                    return None

                def path_after(t_epoch):
                    """ordered (mid) candles strictly after the fill, to settlement."""
                    out = []
                    for ept, mid, _ in cseries:
                        if ept > t_epoch and mid is not None:
                            out.append(mid)
                    return out

                life = ct - ot
                is_longshot_market = False

                for t in trades:
                    if t.get("is_block_trade"):
                        continue
                    # We SELL YES -> we only get filled when a taker BUYS YES (lifts ask)
                    if t.get("taker_side") != "yes":
                        continue
                    p = fnum(t.get("yes_price_dollars"))
                    if p is None or p < LONGSHOT_LO or p > LONGSHOT_HI:
                        continue
                    cnt = fnum(t.get("count_fp"), 0.0)
                    if cnt <= 0:
                        continue
                    tep = parse_ts(t.get("created_time"))
                    if tep is None:
                        continue
                    is_longshot_market = True

                    frac = (tep - ot) / life if life > 0 else 0.5
                    frac = min(max(frac, 0.0), 0.9999)
                    third = THIRDS[min(int(frac * 3), 2)]

                    # maker SOLD yes at p -> short yes. P&L to settle = p - settle.
                    pnl_settle = (p - settle) - fee(p)

                    # ---- (1) entry timing ----
                    third_pnl[third].add(pnl_settle, cnt)
                    third_flow[third] += cnt
                    third_trades[third] += 1

                    # ---- (2) placement ----
                    # The print happened at p (a taker paid p for YES). A resting
                    # YES-sell offer at level L fills iff p >= L.
                    #   improve: L = p - 0.01 (we undercut; we sell 1c cheaper). Fill
                    #            captured at p_improve = p-0.01 (our price).
                    #   touch:   L = p (we sit at touch). captured at p.
                    #   join:    L = p + 0.01 (we ask 1c more). Only fills if the print
                    #            reached p+0.01, i.e. taker paid >= our higher ask.
                    # For each placement we credit expected contracts = cnt*q and book
                    # P&L at OUR fill price.
                    # improve (sell 1c cheaper, more fills, less premium)
                    pi = p - 0.01
                    if pi >= LONGSHOT_LO:
                        pnl_i = (pi - settle) - fee(pi)
                        place_pnl["improve"].add(pnl_i, cnt * Q_IMPROVE)
                        place_flow["improve"] += cnt * Q_IMPROVE
                        place_third_pnl[("improve", third)].add(pnl_i, cnt * Q_IMPROVE)
                    # touch (sell at p)
                    pnl_tch = (p - settle) - fee(p)
                    place_pnl["touch"].add(pnl_tch, cnt * Q_TOUCH)
                    place_flow["touch"] += cnt * Q_TOUCH
                    place_third_pnl[("touch", third)].add(pnl_tch, cnt * Q_TOUCH)
                    # join (sell 1c higher) -- fills only if taker paid >= p+0.01.
                    # A single print at p only *guarantees* fills for L <= p, so a join
                    # at p+0.01 is NOT filled by this print. We approximate join fills as
                    # the share of prints in this market that came at >= our level; here,
                    # conservatively, a print at exactly p does not fill a p+0.01 offer.
                    # (Join is credited below from the >= relationship across prints.)

                    # ---- (4) cadence: this fillable contract is reachable at refresh R
                    # iff our quote was refreshed within R of its placement need. With a
                    # bursty tape, model: a print is captured at refresh R if the touch
                    # didn't move against us since the last refresh boundary. We proxy
                    # "missable" flow by whether the YES ask moved by >1c in the R window
                    # before the print (stale quote => mispriced => either skipped or
                    # adversely filled). Captured fraction estimated via touch stability.
                    cadence_total += cnt
                    for R in REFRESHES:
                        m_before = mid_after  # reuse mid path
                        # mid R minutes before the trade vs at the trade: if stable, we'd
                        # still be correctly quoted and capture it.
                        mb = None
                        target = tep - R * 60
                        best = None
                        for ept, mid, _ in cseries:
                            if ept <= tep and mid is not None:
                                best = mid
                            if ept > tep:
                                break
                        # find mid ~R before
                        prev = None
                        for ept, mid, _ in cseries:
                            if ept <= target and mid is not None:
                                prev = mid
                            if ept > target:
                                break
                        if best is not None and prev is not None:
                            if abs(best - prev) <= 0.01:   # touch stable over R -> captured
                                cadence_capt[R] += cnt
                        else:
                            # not enough candle info: assume captured (conservative for
                            # short R, since most flow is near an active candle)
                            cadence_capt[R] += cnt

                    # ---- (3) hold vs exit ----
                    hold_acc.add(pnl_settle, cnt)
                    path = path_after(tep)
                    # TP: close short when YES mid falls to tp_frac*p (buy back cheap).
                    for tpf in TP_FRACS:
                        target = tpf * p
                        exit_price = None
                        for mid in path:
                            if mid <= target:
                                exit_price = mid
                                break
                        if exit_price is not None:
                            # closed early: P&L = p - exit_price (short yes), minus fees
                            pnl = (p - exit_price) - fee(p) - fee(exit_price)
                        else:
                            pnl = (p - settle) - fee(p)   # never hit TP -> hold to settle
                        tp_acc[tpf].add(pnl, cnt)
                    # STOP: cut when YES mid rises to stop_mult*p (longshot heating up).
                    for sm in STOP_MULTS:
                        target = sm * p
                        exit_price = None
                        for mid in path:
                            if mid >= min(target, 0.99):
                                exit_price = mid
                                break
                        if exit_price is not None:
                            pnl = (p - exit_price) - fee(p) - fee(exit_price)
                        else:
                            pnl = (p - settle) - fee(p)
                        stop_acc[sm].add(pnl, cnt)
                    # combo manager: TP 0.5 OR stop 3.0, whichever first on the path.
                    tp_t = 0.5 * p
                    st_t = min(3.0 * p, 0.99)
                    exitc = None
                    for mid in path:
                        if mid <= tp_t or mid >= st_t:
                            exitc = mid
                            break
                    if exitc is not None:
                        pnl_c = (p - exitc) - fee(p) - fee(exitc)
                    else:
                        pnl_c = (p - settle) - fee(p)
                    combo_acc.add(pnl_c, cnt)

                if is_longshot_market:
                    longshot_markets += 1

                # ---- (2) join placement credited per-market: for every print, a join
                # offer at p+0.01 fills from any *other* print in the same market that
                # came at >= p+0.01. Approximate join as the touch-band realized P&L on
                # prints, haircut by Q_JOIN, booked 1c richer than touch.
                # (done in a second light pass below using the same trades)
                for t in trades:
                    if t.get("is_block_trade") or t.get("taker_side") != "yes":
                        continue
                    p = fnum(t.get("yes_price_dollars"))
                    if p is None or p < LONGSHOT_LO + 0.01 or p > LONGSHOT_HI:
                        continue
                    cnt = fnum(t.get("count_fp"), 0.0)
                    if cnt <= 0:
                        continue
                    tep = parse_ts(t.get("created_time"))
                    if tep is None:
                        continue
                    frac = (tep - ot) / life if life > 0 else 0.5
                    third = THIRDS[min(int(min(max(frac, 0), 0.9999) * 3), 2)]
                    # our join offer was at (p) but the trade that reaches it printed at p;
                    # we book the join 1c richer than a touch sale at p-0.01 baseline:
                    pj = p
                    pnl_j = (pj - settle) - fee(pj)
                    place_pnl["join"].add(pnl_j, cnt * Q_JOIN)
                    place_flow["join"] += cnt * Q_JOIN
                    place_third_pnl[("join", third)].add(pnl_j, cnt * Q_JOIN)

                sys.stderr.write(f"    {tk} r={result} v={fnum(m.get('volume_fp')):.0f} "
                                 f"trades={len(trades)} (mkt#{markets_done})\n")
        if markets_done >= args.max_markets:
            break

    # ---------------------------------------------------------------- report
    def line(name, acc, extra=""):
        return (f"{name:>14s}  n={acc.n:6d}  contracts={acc.contracts:10.0f}  "
                f"VW={acc.vw():+.4f}  TW={acc.tw():+.4f}  se={acc.se():.4f}{extra}")

    R = []
    R.append("==== KALSHI LONGSHOT MAKER -- EXECUTION OPTIMIZER ====")
    R.append(f"markets analyzed: {markets_done} (with candles: {markets_with_candles}); "
             f"longshot-active: {longshot_markets}")
    R.append("by category: " + ", ".join(f"{k}={v}" for k, v in by_cat.items()))
    R.append(f"longshot band YES [{LONGSHOT_LO},{LONGSHOT_HI}]; fee_rate={FEE_RATE} "
             f"(soft cats are zero maker fee)")
    R.append("")
    R.append("(1) ENTRY TIMING -- maker-NO realized P&L to settle, by life-third:")
    tot_flow = sum(third_flow.values()) or 1.0
    for t in THIRDS:
        share = 100.0 * third_flow[t] / tot_flow
        R.append("  " + line(t, third_pnl[t], f"  flow={third_flow[t]:.0f} ({share:.0f}% of fillable)"))
    R.append("")
    R.append("(2) QUOTE PLACEMENT -- realized maker-NO P&L by placement (queue-haircut):")
    R.append(f"    q_improve={Q_IMPROVE}  q_touch={Q_TOUCH}  q_join={Q_JOIN}")
    for pl in PLACEMENTS:
        R.append("  " + line(pl, place_pnl[pl], f"  exp_fills={place_flow[pl]:.0f}"))
    R.append("    edge*fills (relative $ harvested, VW*contracts):")
    for pl in PLACEMENTS:
        harvested = place_pnl[pl].vw() * place_pnl[pl].contracts
        R.append(f"      {pl:>8s}: {harvested:+.1f} (VW {place_pnl[pl].vw():+.4f} x "
                 f"{place_pnl[pl].contracts:.0f} ctr)")
    R.append("")
    R.append("(2b) PLACEMENT x THIRD (VW maker-NO P&L):")
    hdr = "        " + "".join(f"{t:>12s}" for t in THIRDS)
    R.append(hdr)
    for pl in PLACEMENTS:
        row = f"  {pl:>6s}:"
        for t in THIRDS:
            a = place_third_pnl[(pl, t)]
            row += f"  {a.vw():+.4f}" if a.n else f"  {'--':>10s}"
        R.append(row)
    R.append("")
    R.append("(3) HOLD vs EARLY-EXIT -- realized maker-NO P&L per contract:")
    R.append("  " + line("HOLD-to-settle", hold_acc))
    for f in TP_FRACS:
        R.append("  " + line(f"TP@{f:g}xfill", tp_acc[f]))
    for mlt in STOP_MULTS:
        R.append("  " + line(f"STOP@{mlt:g}xfill", stop_acc[mlt]))
    R.append("  " + line("TP0.5+STOP3", combo_acc))
    R.append("")
    R.append("(4) RE-QUOTE CADENCE -- fillable flow reachable at refresh interval:")
    ct = cadence_total or 1.0
    for r in REFRESHES:
        R.append(f"     refresh {r:>3d}min: {100.0*cadence_capt[r]/ct:5.1f}% of fillable flow captured")
    if touch_moves:
        tm = sorted(touch_moves)
        med = tm[len(tm) // 2]
        p90 = tm[int(0.9 * len(tm))]
        frac_move = 100.0 * sum(1 for x in touch_moves if x >= 1.0) / len(touch_moves)
        R.append(f"     touch (yes_ask) minute move: median={med:.2f}c  p90={p90:.2f}c  "
                 f">=1c in {frac_move:.0f}% of minutes")
    R.append("")
    # headline lift: best entry third vs naive (all-thirds touch hold), and best
    # placement vs touch.
    naive = hold_acc.vw()
    best_third = max(THIRDS, key=lambda t: third_pnl[t].vw() if third_pnl[t].n else -9)
    R.append("SUMMARY:")
    R.append(f"  naive (quote-all-life, at-touch, hold-to-settle) VW = {naive:+.4f}/ctr")
    R.append(f"  best entry third = {best_third} (VW {third_pnl[best_third].vw():+.4f}); "
             f"late third VW = {third_pnl['late'].vw():+.4f}")
    R.append(f"  best placement by edge = "
             f"{max(PLACEMENTS, key=lambda p: place_pnl[p].vw() if place_pnl[p].n else -9)}; "
             f"by $ harvested = "
             f"{max(PLACEMENTS, key=lambda p: place_pnl[p].vw()*place_pnl[p].contracts if place_pnl[p].n else -9)}")

    out = "\n".join(R)
    print(out)
    with open("kalshi_longshot_exec_results.txt", "w") as f:
        f.write(out + "\n")

    def d(a):
        return {"n": a.n, "contracts": a.contracts, "vw": a.vw(), "tw": a.tw(), "se": a.se()}
    blob = {
        "markets": markets_done, "with_candles": markets_with_candles,
        "longshot_markets": longshot_markets, "by_cat": dict(by_cat),
        "band": [LONGSHOT_LO, LONGSHOT_HI], "fee_rate": FEE_RATE,
        "q": {"improve": Q_IMPROVE, "touch": Q_TOUCH, "join": Q_JOIN},
        "entry_third": {t: d(third_pnl[t]) for t in THIRDS},
        "entry_third_flow": {t: third_flow[t] for t in THIRDS},
        "placement": {pl: d(place_pnl[pl]) for pl in PLACEMENTS},
        "placement_flow": {pl: place_flow[pl] for pl in PLACEMENTS},
        "placement_third": {f"{pl}|{t}": d(place_third_pnl[(pl, t)])
                            for pl in PLACEMENTS for t in THIRDS},
        "hold": d(hold_acc),
        "tp": {str(f): d(tp_acc[f]) for f in TP_FRACS},
        "stop": {str(mlt): d(stop_acc[mlt]) for mlt in STOP_MULTS},
        "combo_tp0.5_stop3": d(combo_acc),
        "cadence": {str(r): (cadence_capt[r] / (cadence_total or 1)) for r in REFRESHES},
        "touch_move_median_c": (sorted(touch_moves)[len(touch_moves)//2] if touch_moves else None),
    }
    with open("kalshi_longshot_exec_results.json", "w") as f:
        json.dump(blob, f, indent=2)


if __name__ == "__main__":
    main()
