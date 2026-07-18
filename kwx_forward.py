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


def settle():
    plans = _load_jsonl(PLAN_LOG)
    already = {r["ticker"] for r in _load_jsonl(SETTLED)}
    n_new = 0
    with open(SETTLED, "a") as out:
        for p in plans:
            tk = p["ticker"]
            if tk in already:
                continue
            try:
                m = _get(f"{KBASE}/markets/{tk}").get("market", {})
            except Exception:
                continue
            if m.get("status") != "settled" and not m.get("result"):
                continue
            result = m.get("result")  # 'yes'/'no'
            side = p["side"]
            entry = p["cap_c"] / 100.0
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
    print(f"settled {n_new} new paper fires -> {SETTLED}")
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


def report():
    rows = _load_jsonl(SETTLED)
    if not rows:
        print("no settled paper fires yet. Run the runner (kwx_runner.py) live, then `settle`.")
        print(f"(backtest bar to clear: win {EXP_WIN:.1%}, EV +{EXP_EV:.3f}/ct)")
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
