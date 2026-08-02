#!/usr/bin/env python3
"""kwx_forward.py -- FORWARD paper gate + tested==live reconciliation for K-WX (item 9).

Closes the loop the backtest cannot: it takes the LIVE paper fires the runner logged (kwx_runner_plan.jsonl,
each a real-time detection at a real timestamp against real quotes), settles them against Kalshi's actual
result, and compares the realized LIVE paper stats to the BACKTEST expectation. If live == tested (same
win%, same EV within noise), the edge is confirmed out-of-time and we can talk sizing. If live underperforms
tested, that gap IS the adverse-selection / latency cost the backtest couldn't see -- exactly what must be
measured before any capital.

PROPOSE-ONLY: reads logs, fetches public settlement, writes a report. Never trades.

Backtest expectation to beat (Phase-2 Track A, deployable margin=1/sustain=3): win ~99.6%, EV ~+0.207/ct.

Usage:
    python kwx_forward.py settle     # resolve any settled paper fires, append to kwx_forward_settled.jsonl
    python kwx_forward.py report     # live paper stats vs backtest expectation (the tested==live gate)
"""
import json, os, sys, math, urllib.request, ssl, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"
PLAN_LOG = os.path.join(HERE, "kwx_runner_plan.jsonl")
SETTLED = os.path.join(HERE, "kwx_forward_settled.jsonl")

# backtest deployable expectation (the bar live must clear)
EXP_WIN, EXP_EV = 0.9965, 0.2074


def _get(url, to=20):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=to, context=_CTX))


def _kalshi_fee(price_dollars):
    # standard quadratic fee, multiplier 1: 0.07 * p * (1-p), rounded up to the cent per contract
    return math.ceil(0.07 * price_dollars * (1 - price_dollars) * 100) / 100.0


def _load_jsonl(path):
    out = []
    if os.path.exists(path):
        for l in open(path):
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


# Statuses that represent a REAL fill worth scoring. Anything else (a rejection, a guard block, an
# ambiguous send, ...) is NOT a trade and must never reach the win/loss ledger.
_FILL_STATUSES = {"DRY_RUN", "live"}
# Statuses that are DEFINITELY not a fill (used only to label the skip reason; absence from this set
# does not imply "is a fill" -- the real gate is `_is_scoreable`).
_NON_FILL_STATUSES = {"live_error", "blocked", "BLOCKED_HALT", "BLOCKED_SIZE", "BLOCKED_PRICE"}


def _is_scoreable(p):
    """FIX 2 (phantom-win scoring): return (True, None) if plan record `p` represents a REAL fill that may
    be scored, else (False, reason) where reason is 'zero_fill' (filled==0 or None/non-numeric) or
    'non_fill_status' (status is a known non-fill status, e.g. a rejected/blocked order).

    THE BUG THIS FIXES: the old guard was `if p.get("filled") == 0: skip`. A REJECTED order has
    `"filled": null` (None) -- `None == 0` is False in Python, so a rejection slipped straight past the
    guard and was later priced at cap_c and scored as a WIN. That is how kwx_gate_status.txt read
    "settled fires: 2, win rate 100.0%" from ZERO actual fills (see FORWARD_DATA_2026-08-02.md).

    Fix: only a record whose `filled` is a real number > 0 AND whose `status` is a known fill status
    (DRY_RUN or live -- the two statuses buy_yes/buy_no ever set on a record with a numeric fill) is
    scoreable. `filled` not being a number at all (None, missing, or non-numeric) is treated the same as
    filled<=0 -- never falls through to being scored."""
    status = p.get("status")
    # Check status FIRST: a rejected/blocked order (e.g. status="live_error") is a non-fill regardless of
    # what its `filled` field happens to hold (typically None) -- classifying it by status keeps
    # "2 attempted, 0 filled" honest about WHY each record didn't score (rejected vs. genuinely-attempted
    # empty-book dry-run), rather than bucketing everything with a falsy `filled` together.
    if status in _NON_FILL_STATUSES:
        return False, "non_fill_status"
    filled = p.get("filled")
    try:
        filled_n = float(filled) if filled is not None else None
    except (TypeError, ValueError):
        filled_n = None
    if filled_n is None or filled_n <= 0:
        return False, "zero_fill"
    if status not in _FILL_STATUSES:
        # Unknown/unexpected status with a positive filled count -- fail CLOSED (do not score) rather
        # than assume it's a fill just because a number happened to be there.
        return False, "non_fill_status"
    return True, None


def settle():
    plans = _load_jsonl(PLAN_LOG)
    already = {r["ticker"] for r in _load_jsonl(SETTLED)}
    n_new = 0
    n_zero_fill = 0
    n_unfilled = 0   # FIX 2: non-fill statuses (rejections, blocks, ...) distinct from zero_fill dry-runs
    n_no_vwap = 0    # subset of n_unfilled: filled>0 but NO achieved price -> skipped, needs reconciling
    with open(SETTLED, "a") as out:
        for p in plans:
            tk = p["ticker"]
            if tk in already:
                continue
            scoreable, reason = _is_scoreable(p)
            if not scoreable:
                # honest-fill gate hygiene: depth_v1 dry-runs can report filled=0 (public book was empty
                # at fire time -- kwx_runner.py deploys $0 and does NOT mark the rung fired for these, so
                # it can re-fire later with a real fill). A filled=0/None "fire" never actually happened
                # as a trade, so it must NOT be counted as a settled paper fire in the tested==live gate --
                # that would silently inflate n and dilute/pollute win-rate & EV with a phantom position.
                # Skip it (don't even hit the network); a later plan record for the same ticker with
                # filled>0 will settle normally. `n_unfilled` counts non-fill STATUSES (rejections/blocks)
                # separately from `n_zero_fill` (a legitimately-attempted dry-run that saw an empty book)
                # so an operator sees "2 attempted, 0 filled" instead of silence -- see FORWARD_DATA_2026-08-02.md.
                if reason == "non_fill_status":
                    n_unfilled += 1
                else:
                    n_zero_fill += 1
                continue
            try:
                m = _get(f"{KBASE}/markets/{tk}").get("market", {})
            except Exception:
                continue
            if m.get("status") != "settled" and not m.get("result"):
                continue
            result = m.get("result")  # 'yes'/'no'
            side = p["side"]
            # entry price: the depth_v1 simulated/actual fill VWAP -- the price we ACTUALLY paid walking
            # the book. FIX 2: NO fallback to cap_c. cap_c is a requested cap, never an achieved price;
            # falling back to it for a record that somehow reached scoring without a real vwap would
            # manufacture a fake entry price for a fill we never actually priced (the same class of bug
            # as the phantom-win guard above). If fill_vwap_c is missing here, skip -- don't guess.
            if p.get("fill_vwap_c") is None:
                # Counted separately from the rejections above and reported with its own line: this branch
                # is NOT "no trade happened". It is a record that PASSED _is_scoreable (status DRY_RUN/live
                # AND filled>0) but carries no achieved price -- i.e. an assumed_full dry-run (public book
                # unreadable at fire time) or, on the live path, a fill whose average_fill_price was absent
                # or unparseable. The latter means we may actually HOLD contracts that are now missing from
                # the P&L ledger, which an operator must be able to see and reconcile; lumping it in with
                # "rejected/blocked" would hide exactly that. (Still skipped, never priced at cap_c.)
                n_no_vwap += 1
                n_unfilled += 1
                continue
            entry = p["fill_vwap_c"] / 100.0
            fee = _kalshi_fee(entry)
            # we bought `side`; we win if result == side
            won = (result == side)
            pnl = (1.0 - entry - fee) if won else (-entry - fee)
            rec = {**p, "result": result, "won": won, "entry": entry, "fee": fee, "pnl": pnl}
            out.write(json.dumps(rec) + "\n")
            already.add(tk)
            n_new += 1
            try:
                import kwx_notify
                emoji = "✅" if won else "❌"
                kwx_notify.alert(f"{emoji} KWX SETTLE: {tk} -> {result} (bought {side}@{entry*100:.0f}¢) "
                                 f"PnL {pnl:+.2f}/ct")
            except Exception:
                pass
    print(f"settled {n_new} new paper fires -> {SETTLED}"
          + (f"  ({n_zero_fill} zero-fill plan(s) skipped -- book was empty, not counted toward the gate)"
             if n_zero_fill else "")
          + (f"  ({n_unfilled - n_no_vwap} unfilled/non-fill plan(s) skipped -- rejected/blocked, "
             f"not counted toward the gate)" if (n_unfilled - n_no_vwap) else ""))
    if n_no_vwap:
        print(f"  !! {n_no_vwap} plan(s) reported filled>0 but NO fill_vwap_c -- skipped (never priced at "
              f"cap_c). If any of these were LIVE fills you may hold contracts that are NOT in the P&L "
              f"ledger: reconcile by client_order_id against the portfolio before trusting the gate.")
    if n_new:
        try:
            import kwx_notify
            rows = _load_jsonl(SETTLED)
            wins = sum(1 for r in rows if r.get("won"))
            tot = sum(r["pnl"] for r in rows)
            kwx_notify.alert(f"📊 KWX running: {len(rows)} settled, {wins}/{len(rows)} won, "
                             f"cum PnL {tot:+.2f}/ct")
        except Exception:
            pass
    return n_new, n_zero_fill, n_unfilled


def _plan_fill_tally():
    """All-time tally over PLAN_LOG of zero-fill vs non-fill(rejected/blocked) plan records (FIX 2), so
    report()/kwx_paper_gate can surface "N attempted, 0 filled" instead of silence -- this is the
    dangerous case: a run of nothing-but-rejections must be visibly distinguishable from a quiet market,
    not just absent from the settled ledger. Independent of settle()'s already-processed bookkeeping --
    recomputed fresh each call so it reflects the CURRENT plan log regardless of settle ordering."""
    n_zero_fill = n_unfilled = n_scoreable = 0
    for p in _load_jsonl(PLAN_LOG):
        ok, reason = _is_scoreable(p)
        if ok:
            n_scoreable += 1
        elif reason == "non_fill_status":
            n_unfilled += 1
        else:
            n_zero_fill += 1
    return {"n_zero_fill": n_zero_fill, "n_unfilled": n_unfilled, "n_scoreable": n_scoreable}


def report():
    rows = _load_jsonl(SETTLED)
    tally = _plan_fill_tally()   # FIX 2: surface zero-fill AND non-fill(rejected/blocked) counts, always
    if not rows:
        print("no settled paper fires yet. Run the runner (kwx_runner.py) live, then `settle`.")
        print(f"(backtest bar to clear: win {EXP_WIN:.1%}, EV +{EXP_EV:.3f}/ct)")
        print(f"  plan log       : {tally['n_scoreable']} attempted with a real fill, "
              f"{tally['n_zero_fill']} zero-fill (empty book), {tally['n_unfilled']} rejected/blocked")
        return
    pnls = [r["pnl"] for r in rows]
    wins = sum(1 for r in rows if r["won"])
    n = len(rows)
    # day-clustered t
    byday = defaultdict(list)
    for r in rows:
        byday[r.get("date", "?")].append(r["pnl"])
    daymeans = [st.mean(v) for v in byday.values()]
    t = (st.mean(daymeans) / (st.stdev(daymeans) / math.sqrt(len(daymeans)))
         if len(daymeans) > 1 and st.stdev(daymeans) > 0 else float("nan"))
    ev = st.mean(pnls)
    print("=== K-WX FORWARD PAPER (tested==live gate) ===")
    print(f"  n fires        : {n}   ({len(byday)} days)")
    print(f"  win rate       : {wins/n:.1%}   (backtest {EXP_WIN:.1%})")
    print(f"  EV/ct net-fee  : {ev:+.3f}   (backtest +{EXP_EV:.3f})")
    print(f"  day-clustered t: {t:.2f}")
    print(f"  worst fire     : {min(pnls):+.3f}")
    print(f"  n_zero_fill    : {tally['n_zero_fill']}   (empty book at fire time -- not scored)")
    print(f"  n_unfilled     : {tally['n_unfilled']}   (rejected/blocked -- not scored)")
    gap_ev = ev - EXP_EV
    verdict = ("LIVE MATCHES TESTED (edge holds out-of-time)" if abs(gap_ev) < 0.05 and wins/n >= EXP_WIN - 0.02
               else "LIVE UNDERPERFORMS TESTED -- gap = adverse-selection/latency cost" if gap_ev < -0.05
               else "ACCRUING (need more fires for a clustered verdict)" if n < 30 else "MIXED -- inspect")
    print(f"  VERDICT        : {verdict}")
    if n < 30:
        print("  (n<30: not yet decisive; keep the runner accruing.)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    if mode == "settle":
        settle()
    else:
        report()
