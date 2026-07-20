#!/usr/bin/env python3
"""wx_earlylock_decision.py -- DECISION LAYER for the "early-lock" refinement forward price-check.

WHY: wx_earlylock_study.py proved early-lock is PREDICTABLE (thr-0.95 -> ~96.88% pooled win, ~60 min lead
over the mechanical lock). wx_earlylock_forward.py measures the still-open question -- PRICE: does the live
market actually offer those early rungs below the ~95.3c break-even, or has it already priced the identical
forecast to >=96c ("dead")? This module is the gate that turns that forward measurement into a decision, so
the strategy can self-activate the moment (and only the moment) the data actually supports it, instead of
someone having to eyeball `wx_earlylock_forward.py report` and judgment-call it.

It reads ONLY wx_earlylock_settled.jsonl (paper, no orders, no credentials) and emits exactly one verdict:

  ACTIVATE-PAPER  -- forward data clears a conservative bar (see BAR below): build the real paper harness.
  ACCRUING        -- not enough evidence yet either way; reports n so far + an honest ETA at the observed
                     live signal rate (NOT the backtest rate -- see wx_earlylock_accrual.md for why those
                     differ).
  DEAD            -- enough evidence that the market already prices the signal (mean captured ask sits at or
                     above the break-even even under an OPTIMISTIC read of the data); early-lock does not beat
                     the deployed mechanical-lock baseline at the prices actually on offer.

FEE TREATMENT: every settled row's `pnl` field is already net of the standard Kalshi quadratic taker fee,
computed by wx_earlylock_forward._kalshi_fee() at the LOGGED yes_ask (ceil(0.07*p*(1-p)*100)/100, same
formula as wx_forecast_forward and kwx_runner's paper accounting) -- this module never recomputes fee for the
observed EV, it just aggregates `pnl`. It DOES recompute fee once, at the mean captured ask, for the
conservative (Wilson-lower-bound) EV bound below, since that bound is a hypothetical re-weighting of win rate
at the observed price, not a replay of individual rows.

STATISTICS: win rate is reported both as the raw point estimate and as a two-sided 95% Wilson score interval
(conservative for small n, doesn't misbehave at p near 0/1 the way a normal approximation does). Significance
uses a day-clustered one-sample t-test on per-day mean pnl (one row's fluke day cannot drive the verdict) --
same construction as wx_earlylock_forward.report()'s "day-clustered t" and kwx_paper_gate's gate stat.

CONSERVATIVE BAR (mirrors kwx_paper_gate.PASS's style: a hold-out bar stricter than the raw estimate, so a
pass is a real signal, not n=1 noise):
  win >= WIN_BAR (Wilson LOWER bound, not the raw mean)     -- the pessimistic win rate must still be high
  ev  >= EV_BAR  (using the Wilson LOWER bound win rate at the mean captured price, net of fee)
                                                             -- beats the deployed mechanical-lock baseline
                                                                (BASELINE_EV_C, imported from the forward
                                                                module) even under the pessimistic read
  n   >= N_BAR                                               -- enough settled fires to trust an average
  t   >= T_BAR                                               -- day-clustered significance, not one lucky day

DEAD is the mirror check in the OTHER direction: even the OPTIMISTIC read (Wilson UPPER bound win rate) does
not beat the baseline, and n is already large enough (N_DEAD) that this isn't just early noise.

NO LIVE TRADING INTEGRATION: this script only ever reads wx_earlylock_settled.jsonl and prints a verdict. It
never places orders, never reads credentials, never sets KWX_LIVE, and does not modify kwx_runner / kwx_exec /
kwx_paper_gate in any way. ACTIVATE-PAPER means "build a paper harness for this sleeve next," not "go live."

Usage:
    python wx_earlylock_decision.py
"""
import math
import statistics as stt
from collections import defaultdict

import wx_earlylock_forward as F   # reuse SETTLED path, THR, BASELINE_EV_C, BREAKEVEN_C, _kalshi_fee, _load_jsonl

# ---------------- conservative activation bar ----------------
WIN_BAR = 0.90          # Wilson LOWER bound win rate must clear this (well below the study's 96.88% point
                         # estimate, on purpose -- this is a floor, not the expectation)
EV_BAR = F.BASELINE_EV_C  # conservative EV (cents/ct, Wilson-lower-bound win rate at mean captured price, net
                           # of fee) must beat the deployed mechanical-lock baseline, not just be positive
N_BAR = 30               # settled fires -- matches kwx_paper_gate's own n>=30 bar for the same reason
T_BAR = 3.0              # day-clustered t -- matches kwx_paper_gate's own t>=3 bar

# ---------------- "dead" (market already prices it in) bar ----------------
N_DEAD = 30              # need at least this many settled fires before DEAD is a supportable claim (an early
                          # run of expensive asks could just be an unlucky sample, not "priced in")


def wilson_ci(k, n, z=1.96):
    """Two-sided Wilson score CI for a binomial proportion k/n (default z=1.96 -> 95%). Same formula as
    wx_ev_concentration.wilson_ci / kalshi_weather_nowcast.wilson_upper_bound; conservative and well-behaved
    at small n / p near 0 or 1, unlike a normal approximation."""
    if n <= 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def day_clustered_t(rows):
    """One-sample t-test on per-day mean pnl (day-clustered, guards against one lucky/unlucky day). Returns
    (t, n_days); t is NaN if fewer than 2 days or zero variance (mirrors wx_earlylock_forward.report())."""
    byday = defaultdict(list)
    for r in rows:
        byday[r["date"]].append(r["pnl"])
    dm = [stt.mean(v) for v in byday.values()]
    if len(dm) > 1 and stt.stdev(dm) > 0:
        return stt.mean(dm) / (stt.stdev(dm) / math.sqrt(len(dm))), len(dm)
    return float("nan"), len(dm)


def _accrual_rate_per_day(paper_rows):
    """Observed LIVE signal rate (paper rows/day since the first logged row), for an honest ETA. Deliberately
    uses the forward harness's own accrual, NOT the backtest study's synthetic-strike-offset signal count --
    those measure different things (see wx_earlylock_accrual.md: the study sweeps extreme+/-1..5 offsets to
    build a frontier; the forward harness only logs the ONE strike actually on the live ladder that the
    deployed mechanical-lock buys). Returns (rate_per_day, n_days_observed, n_rows)."""
    if not paper_rows:
        return 0.0, 0.0, 0
    dates = sorted(r["date"] for r in paper_rows)
    import datetime as dt
    d0 = dt.date.fromisoformat(dates[0])
    d1 = dt.date.fromisoformat(dates[-1])
    span_days = max(1.0, (d1 - d0).days + 1)   # inclusive span; floor of 1 day so a same-day rate isn't inf
    return len(paper_rows) / span_days, span_days, len(paper_rows)


def compute():
    """Pull everything the verdict needs into one dict. Never raises: an empty/missing settled log just
    yields n=0 (ACCRUING), matching wx_earlylock_forward.report()'s own no-data path."""
    settled = F._load_jsonl(F.SETTLED)
    paper = F._load_jsonl(F.PAPER)
    n = len(settled)
    out = {
        "n": n, "n_paper_logged": len(paper),
        "rate_per_day": 0.0, "span_days": 0.0, "eta_days": None,
    }
    rate, span, _ = _accrual_rate_per_day(paper)
    out["rate_per_day"], out["span_days"] = rate, span
    if n == 0:
        out["eta_days"] = ((N_BAR - 0) / rate) if rate > 0 else float("inf")
        return out

    wins = sum(1 for r in settled if r["won"])
    pnls = [r["pnl"] for r in settled]
    asks = [r["yes_ask_c"] for r in settled]
    win_pt = wins / n
    win_lo, win_hi = wilson_ci(wins, n)
    mean_ask_c = stt.mean(asks)
    mean_price = mean_ask_c / 100.0
    fee_c = F._kalshi_fee(mean_price) * 100.0
    ev_observed_c = stt.mean(pnls) * 100.0                       # point-estimate EV, net of fee (raw pnl)
    ev_conservative_c = win_lo * 100.0 - mean_ask_c - fee_c        # Wilson-LOWER win rate at mean captured ask
    ev_optimistic_c = win_hi * 100.0 - mean_ask_c - fee_c          # Wilson-UPPER win rate at mean captured ask
    t, n_days = day_clustered_t(settled)

    bykind = defaultdict(list)
    for r in settled:
        bykind[r.get("kind", "max")].append(r)

    out.update({
        "n_days": n_days, "wins": wins,
        "win_pt": win_pt, "win_lo": win_lo, "win_hi": win_hi,
        "mean_ask_c": mean_ask_c, "fee_c": fee_c,
        "ev_observed_c": ev_observed_c, "ev_conservative_c": ev_conservative_c,
        "ev_optimistic_c": ev_optimistic_c, "t": t,
        "worst_pnl_c": min(pnls) * 100.0, "best_pnl_c": max(pnls) * 100.0,
        "bykind": {k: {"n": len(v), "win": sum(1 for r in v if r["won"]) / len(v),
                        "mean_ask": stt.mean([r["yes_ask_c"] for r in v])} for k, v in bykind.items()},
    })
    out["eta_days"] = ((N_BAR - n) / rate) if (n < N_BAR and rate > 0) else (0.0 if n >= N_BAR else float("inf"))
    return out


def verdict(m):
    """Return (label, reason_str). ACTIVATE-PAPER / DEAD require n>=their bar; anything short is ACCRUING."""
    n = m["n"]
    if n >= N_BAR and n > 0:
        # t is NaN only when there's <=1 distinct day or zero day-to-day variance; with n>=N_BAR that would
        # itself be a red flag (all fires piled into one day), so NaN never silently passes here.
        t_ok = isinstance(m["t"], float) and m["t"] == m["t"] and m["t"] >= T_BAR
        if m["win_lo"] >= WIN_BAR and m["ev_conservative_c"] >= EV_BAR and t_ok:
            return ("ACTIVATE-PAPER",
                    f"conservative bar cleared: win Wilson-lo {m['win_lo']:.1%} >= {WIN_BAR:.0%}, "
                    f"EV(conservative) {m['ev_conservative_c']:+.2f}c >= {EV_BAR:+.1f}c baseline, "
                    f"n={n} >= {N_BAR}, day-clustered t={m['t']:.2f} >= {T_BAR:.1f}")
    if n >= N_DEAD and m["ev_optimistic_c"] < F.BASELINE_EV_C:
        return ("DEAD",
                f"even the OPTIMISTIC read doesn't clear baseline: EV(Wilson-hi win {m['win_hi']:.1%}) "
                f"{m['ev_optimistic_c']:+.2f}c < {F.BASELINE_EV_C:+.1f}c baseline at mean captured ask "
                f"{m['mean_ask_c']:.1f}c (break-even {F.BREAKEVEN_C:.1f}c), n={n}")
    eta = m.get("eta_days")
    eta_str = ("unknown -- zero live signal rate so far" if not eta or eta == float("inf")
               else f"~{eta:.0f} days at the observed live rate ({m['rate_per_day']:.2f} signals/day "
                    f"over {m['span_days']:.1f} days so far)")
    return ("ACCRUING", f"n={n} settled (need {N_BAR} to ACTIVATE or {N_DEAD} to rule DEAD); "
                         f"{m['n_paper_logged']} paper rows logged total; honest ETA to n={N_BAR}: {eta_str}")


def print_report(m, v):
    label, reason = v
    print("=" * 96)
    print("EARLY-LOCK DECISION LAYER -- does the forward price data support activating a paper harness?")
    print("=" * 96)
    print(f"  settled fires        : {m['n']}" + (f"  ({m['n_days']} days)" if m['n'] else ""))
    print(f"  paper rows logged    : {m['n_paper_logged']} total")
    print(f"  observed signal rate : {m['rate_per_day']:.2f}/day over {m['span_days']:.1f} days")
    if m["n"]:
        print(f"  win rate             : {m['win_pt']:.1%} pt-est   "
              f"[{m['win_lo']:.1%}, {m['win_hi']:.1%}] Wilson 95% CI   (study claim @ thr-{F.THR}: ~96.88%)")
        print(f"  mean captured ask    : {m['mean_ask_c']:.1f}c   (break-even to beat baseline <= {F.BREAKEVEN_C:.1f}c)")
        print(f"  EV / contract        : observed {m['ev_observed_c']:+.2f}c   "
              f"conservative(Wilson-lo) {m['ev_conservative_c']:+.2f}c   "
              f"optimistic(Wilson-hi) {m['ev_optimistic_c']:+.2f}c   vs baseline {F.BASELINE_EV_C:+.1f}c")
        print(f"  day-clustered t      : {m['t']:.2f}   (bar {T_BAR:.1f})")
        print(f"  worst / best pnl     : {m['worst_pnl_c']:+.1f}c / {m['best_pnl_c']:+.1f}c")
        if m.get("bykind"):
            print("  by case (HIGH=max/LOW=min):")
            for k in ("max", "min"):
                s = m["bykind"].get(k)
                if s:
                    print(f"    {k:<4} n={s['n']:<4} win={s['win']:.1%}  mean_ask={s['mean_ask']:.1f}c")
    print(f"\n  BAR (ACTIVATE-PAPER): win Wilson-lo >= {WIN_BAR:.0%}, EV(conservative) >= {EV_BAR:+.1f}c, "
          f"n >= {N_BAR}, day-clustered t >= {T_BAR:.1f}")
    print(f"  BAR (DEAD)          : n >= {N_DEAD} AND EV(optimistic) < {F.BASELINE_EV_C:+.1f}c")
    print()
    print(f"  VERDICT: {label}")
    print(f"  reason : {reason}")
    print("=" * 96)


def main():
    m = compute()
    v = verdict(m)
    print_report(m, v)
    return v[0]


def one_line():
    """Compact summary for kwx_daily_digest.py's fail-soft digest line: `earlylock: <verdict summary>`."""
    m = compute()
    label, reason = verdict(m)
    if label == "ACCRUING":
        return f"{label} (n={m['n']}/{N_BAR} settled, {m['n_paper_logged']} logged, ETA {reason.rsplit(': ', 1)[-1]})"
    if label == "ACTIVATE-PAPER":
        return f"{label} (n={m['n']}, win-lo {m['win_lo']:.1%}, EV-cons {m['ev_conservative_c']:+.2f}c)"
    return f"{label} (n={m['n']}, mean ask {m['mean_ask_c']:.1f}c vs break-even {F.BREAKEVEN_C:.1f}c)"


if __name__ == "__main__":
    main()
