#!/usr/bin/env python3
"""wx_forecast_decision.py -- DECISION LAYER for the forecast-overlay sleeve (wx_forecast_forward.py).

WHY: FORECAST_OVERLAY_BACKTEST.md's Fable adversarial verification REFUTED both backtests behind this sleeve
-- their apparent edge (+0.114 to +0.203c/ct, t=11-18 over 178-427 distinct days) was entirely a look-ahead
artifact (Open-Meteo's day-0 historical-forecast archive is built from intraday runs issued after the
sleeve's actual morning decision window). The honest rerun, using genuinely pre-issued lead-1 forecasts on
Impl A's exact pipeline, gives EV -0.016c/ct, day-clustered t=-1.74 over the same 178 distinct days -- a null,
not a proven edge. That verified backtest number is the BAR this module encodes: it is the number any future
forward (live paper) evidence has to beat before this sleeve is worth reconsidering at all.

This module is the mirror of wx_earlylock_decision.py / wx_maker_deep_study.md's gate pattern for a sleeve
whose *backtest itself* already failed, not one still waiting on its first real-world read:

  KILL        -- the forward paper log (wx_forecast_settled.jsonl), read with n large enough to trust, ALSO
                 fails to beat the backtest bar even under an OPTIMISTIC (Wilson-upper) read. Sleeve fully
                 retired -- stop reporting it as a candidate.
  RECONSIDER  -- the forward paper log clears a strict CONSERVATIVE (Wilson-lower) bar with enough distinct
                 days and significance to overturn the backtest refutation. Treated with heavy skepticism by
                 design (see BAR below) -- this would mean live reality disagrees with a fairly powered null,
                 which itself would need a fresh adversarial look before touching any live/paper harness.
  ACCRUING    -- neither bar is cleared yet (the default state; this will be true for a long time given the
                 backtest already found nothing). Reports n so far + an honest ETA at the observed live rate.

FEE / PNL TREATMENT -- IMPORTANT DEVIATION FROM THE RAW LOG: wx_forecast_forward.settle() has a known bug
(FORECAST_OVERLAY_BACKTEST.md Section 3): it prices EVERY settled row, including side=="no" rows, using the
yes_ask as the cost basis (`pnl = 1-price-fee if won else -price-fee`), which is only correct for side=="yes".
For a NO position the cost basis should be the NO price, approximated here as `1 - yes_ask` (no separate
no-side book was captured at snapshot time, so this is the best available proxy -- same complement Kalshi
itself uses when only one side's book is quoted). This module NEVER trusts the logged `pnl` field; it always
recomputes pnl per row from (side, price, won) with the corrected formula, so a known accounting bug in the
upstream harness cannot silently inflate this gate's verdict (this is exactly the bug that manufactures the
sleeve's apparent +0.217/trade, 2-calendar-day live paper number -- see the backtest doc). The Kalshi fee
formula itself (ceil(7*p*(1-p))/100, applied at whichever price is the true cost basis for that side) is
unchanged from wx_forecast_forward._kalshi_fee.

STATISTICS: win rate as raw point estimate + two-sided 95% Wilson score interval (small-n safe, doesn't
misbehave near p=0/1). Significance via a day-clustered one-sample t-test on per-day mean pnl (same
construction as wx_earlylock_forward.report() / wx_earlylock_decision.py -- same-day fires across
cities/rungs are not independent draws, so day is the clustering unit, not row).

NO LIVE TRADING INTEGRATION: reads only wx_forecast_paper.jsonl / wx_forecast_settled.jsonl and prints a
verdict. Never places orders, never reads credentials, never touches kwx_runner.py / kwx_paper_gate.py /
kalshi_exec.py. RECONSIDER means "worth a fresh adversarial look," not "go live."

Usage:
    python wx_forecast_decision.py
"""
import math
import statistics as stt
from collections import defaultdict

import wx_forecast_forward as F   # reuse SETTLED/PAPER paths, _kalshi_fee, _load_jsonl

# ---------------- the verified backtest bar (FORECAST_OVERLAY_BACKTEST.md, honest lead-1 rerun) ----------------
BACKTEST_EV_C = -1.6          # cents/contract, honest-cost, no-look-ahead (Impl A pipeline, lead-1 forecasts)
BACKTEST_T = -1.74            # day-clustered t on that rerun
BACKTEST_N_DAYS = 178         # distinct days behind the honest rerun
BACKTEST_WIN_RATE = 0.396     # win rate, honest rerun

# ---------------- conservative bar for RECONSIDER (mirrors wx_earlylock_decision's WIN_BAR/EV_BAR/N_BAR/T_BAR
# style, but stricter: this sleeve's own backtest already came back null, so flipping to RECONSIDER should
# require the forward evidence to be UNAMBIGUOUSLY positive, not merely "not obviously negative") ----------------
EV_BAR_C = 2.0            # conservative (Wilson-lower-bound win rate) EV must clear this, in cents/contract --
                           # comfortably above 0 and above the backtest's -1.6c, so a pass is a real reversal
N_BAR = 40                 # distinct days -- higher than wx_earlylock_decision's n=30 fires bar precisely
                            # because this is by DISTINCT DAY (house rule: same-day fires are not independent)
                            # and because reopening an already-refuted result should take more, not less,
                            # evidence than a fresh sleeve's first activation gate
T_BAR = 3.0                # day-clustered t -- matches house convention (kwx_paper_gate, wx_earlylock_decision)

# ---------------- "confirmed KILL" bar: enough clean forward days that failing to beat the bar even under the
# optimistic read is a real second confirmation, not early noise ----------------
N_KILL = 40


def wilson_ci(k, n, z=1.96):
    """Two-sided Wilson score CI for a binomial proportion k/n. Same formula as wx_earlylock_decision.wilson_ci
    / wx_ev_concentration.wilson_ci -- conservative and well-behaved at small n / p near 0 or 1."""
    if n <= 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def _honest_pnl(row):
    """Recompute pnl per row from raw fields, correcting wx_forecast_forward.settle()'s NO-side cost-basis
    bug (FORECAST_OVERLAY_BACKTEST.md Section 3). `price` in the log is always the captured YES price at
    snapshot time, regardless of side. For side=='yes' the original formula is already correct; for
    side=='no' the true cost basis is the NO price, approximated as (1 - yes price) since no separate NO
    book was captured. Returns (pnl, cost_basis)."""
    price = row["price"]
    won = row["won"]
    side = row.get("side", "yes")
    cost = price if side == "yes" else (1.0 - price)
    fee = F._kalshi_fee(cost)
    pnl = (1.0 - cost - fee) if won else (-cost - fee)
    return pnl, cost


def day_clustered_t(pnls_by_day):
    """One-sample t-test on per-day mean pnl. Returns (t, n_days); NaN if <2 days or zero variance."""
    dm = [stt.mean(v) for v in pnls_by_day.values() if v]
    if len(dm) > 1 and stt.stdev(dm) > 0:
        return stt.mean(dm) / (stt.stdev(dm) / math.sqrt(len(dm))), len(dm)
    return float("nan"), len(dm)


def _accrual_rate_per_day(paper_rows):
    """Observed LIVE snapshot rate (paper rows/day since the first logged row), for an honest ETA. Mirrors
    wx_earlylock_decision._accrual_rate_per_day."""
    if not paper_rows:
        return 0.0, 0.0, 0
    dates = sorted(r["date"] for r in paper_rows)
    import datetime as dt
    d0 = dt.date.fromisoformat(dates[0])
    d1 = dt.date.fromisoformat(dates[-1])
    span_days = max(1.0, (d1 - d0).days + 1)
    return len(paper_rows) / span_days, span_days, len(paper_rows)


def compute():
    """Pull everything the verdict needs into one dict. Never raises: an empty/missing settled log just
    yields n_days=0 (ACCRUING), matching wx_earlylock_decision.compute()'s no-data path. Distinct DAYS, not
    rows, is the accrual unit throughout (house rule: same-day fires across cities/rungs are not independent)."""
    settled = F._load_jsonl(F.SETTLED)
    paper = F._load_jsonl(F.PAPER)
    out = {
        "n_rows": len(settled), "n_paper_logged": len(paper),
        "rate_per_day": 0.0, "span_days": 0.0, "eta_days": None,
        "n_days": 0,
    }
    rate, span, _ = _accrual_rate_per_day(paper)
    out["rate_per_day"], out["span_days"] = rate, span
    if not settled:
        out["eta_days"] = ((N_BAR - 0) / rate) if rate > 0 else float("inf")
        return out

    byday = defaultdict(list)
    wins = 0
    for r in settled:
        pnl, cost = _honest_pnl(r)
        byday[r["date"]].append(pnl)
        if r["won"]:
            wins += 1
    n_days = len(byday)
    n = len(settled)
    win_pt = wins / n
    win_lo, win_hi = wilson_ci(wins, n)
    all_pnls = [p for v in byday.values() for p in v]
    ev_observed_c = stt.mean(all_pnls) * 100.0
    # conservative/optimistic EV bounds: re-weight the observed mean cost basis at the Wilson win-rate bounds,
    # net of fee at that same cost -- same construction as wx_earlylock_decision's ev_conservative/optimistic.
    mean_cost = stt.mean([_honest_pnl(r)[1] for r in settled])
    fee_c = F._kalshi_fee(mean_cost) * 100.0
    ev_conservative_c = win_lo * 100.0 - mean_cost * 100.0 - fee_c
    ev_optimistic_c = win_hi * 100.0 - mean_cost * 100.0 - fee_c
    t, _ = day_clustered_t(byday)

    out.update({
        "n_days": n_days, "wins": wins, "win_pt": win_pt, "win_lo": win_lo, "win_hi": win_hi,
        "mean_cost_c": mean_cost * 100.0, "fee_c": fee_c,
        "ev_observed_c": ev_observed_c, "ev_conservative_c": ev_conservative_c,
        "ev_optimistic_c": ev_optimistic_c, "t": t,
        "worst_pnl_c": min(all_pnls) * 100.0, "best_pnl_c": max(all_pnls) * 100.0,
    })
    out["eta_days"] = ((N_BAR - n_days) / rate) if (n_days < N_BAR and rate > 0) else (0.0 if n_days >= N_BAR else float("inf"))
    return out


def verdict(m):
    """Return (label, reason_str). RECONSIDER/KILL both require n_days >= their bar; anything short (which,
    given the backtest already refuted this sleeve, is the expected long-run default) is ACCRUING."""
    n_days = m["n_days"]
    if n_days >= N_BAR and n_days > 0:
        t_ok = isinstance(m["t"], float) and m["t"] == m["t"] and m["t"] >= T_BAR
        if m["win_lo"] > 0 and m["ev_conservative_c"] >= EV_BAR_C and t_ok:
            return ("RECONSIDER",
                    f"forward evidence clears the reversal bar: EV(conservative) {m['ev_conservative_c']:+.2f}c "
                    f">= {EV_BAR_C:+.1f}c, n_days={n_days} >= {N_BAR}, day-clustered t={m['t']:.2f} >= {T_BAR:.1f} "
                    f"-- this DISAGREES with the honest backtest rerun (EV {BACKTEST_EV_C:+.1f}c, t={BACKTEST_T:.2f}, "
                    f"{BACKTEST_N_DAYS} days); treat as a trigger for a fresh adversarial look, not a green light")
    if n_days >= N_KILL and m["ev_optimistic_c"] < EV_BAR_C:
        return ("KILL",
                f"forward paper log confirms the backtest refutation: even the OPTIMISTIC read "
                f"(Wilson-hi win {m['win_hi']:.1%}) gives EV {m['ev_optimistic_c']:+.2f}c < {EV_BAR_C:+.1f}c bar, "
                f"n_days={n_days} >= {N_KILL}. Backtest (honest rerun): EV {BACKTEST_EV_C:+.1f}c, "
                f"t={BACKTEST_T:.2f}, {BACKTEST_N_DAYS} days, win {BACKTEST_WIN_RATE:.1%}. Sleeve retired.")
    eta = m.get("eta_days")
    eta_str = ("unknown -- zero live snapshot rate so far" if not eta or eta == float("inf")
               else f"~{eta:.0f} days at the observed live rate ({m['rate_per_day']:.2f} rows/day "
                    f"over {m['span_days']:.1f} days so far)")
    return ("ACCRUING",
            f"n_days={n_days} settled (need {N_BAR} distinct days to RECONSIDER or {N_KILL} to confirm KILL); "
            f"backtest already REFUTED this sleeve (honest rerun EV {BACKTEST_EV_C:+.1f}c, t={BACKTEST_T:.2f}, "
            f"{BACKTEST_N_DAYS} days) -- that is the standing bar until forward data says otherwise; "
            f"{m['n_paper_logged']} paper rows logged total; honest ETA to n_days={N_BAR}: {eta_str}")


def print_report(m, v):
    label, reason = v
    print("=" * 100)
    print("FORECAST-OVERLAY DECISION LAYER -- backtest REFUTED (see FORECAST_OVERLAY_BACKTEST.md); does forward")
    print("paper evidence beat that bar?")
    print("=" * 100)
    print(f"  backtest bar (honest, no-look-ahead): EV {BACKTEST_EV_C:+.1f}c/ct, day-clustered t={BACKTEST_T:.2f}, "
          f"{BACKTEST_N_DAYS} distinct days, win {BACKTEST_WIN_RATE:.1%}")
    print(f"  settled rows          : {m['n_rows']}   ({m['n_days']} distinct days)")
    print(f"  paper rows logged     : {m['n_paper_logged']} total")
    print(f"  observed snapshot rate: {m['rate_per_day']:.2f}/day over {m['span_days']:.1f} days")
    if m["n_rows"]:
        print(f"  win rate              : {m['win_pt']:.1%} pt-est   [{m['win_lo']:.1%}, {m['win_hi']:.1%}] Wilson 95% CI")
        print(f"  mean cost basis       : {m['mean_cost_c']:.1f}c   (side-corrected -- see module docstring Section 3 bug)")
        print(f"  EV / contract (honest): observed {m['ev_observed_c']:+.2f}c   "
              f"conservative(Wilson-lo) {m['ev_conservative_c']:+.2f}c   optimistic(Wilson-hi) {m['ev_optimistic_c']:+.2f}c")
        print(f"  day-clustered t       : {m['t']:.2f}   (RECONSIDER bar {T_BAR:.1f})")
        print(f"  worst / best pnl      : {m['worst_pnl_c']:+.1f}c / {m['best_pnl_c']:+.1f}c")
    print(f"\n  BAR (RECONSIDER): win Wilson-lo > 0%, EV(conservative) >= {EV_BAR_C:+.1f}c, n_days >= {N_BAR}, "
          f"day-clustered t >= {T_BAR:.1f}")
    print(f"  BAR (KILL)      : n_days >= {N_KILL} AND EV(optimistic) < {EV_BAR_C:+.1f}c")
    print()
    print(f"  VERDICT: {label}")
    print(f"  reason : {reason}")
    print("=" * 100)


def main():
    m = compute()
    v = verdict(m)
    print_report(m, v)
    return v[0]


def one_line():
    """Compact summary for kwx_daily_digest.py's fail-soft digest line: `forecast: <verdict summary>`."""
    m = compute()
    label, reason = verdict(m)
    if label == "ACCRUING":
        return f"{label} (n_days={m['n_days']}/{N_BAR}, backtest bar EV {BACKTEST_EV_C:+.1f}c t={BACKTEST_T:.2f})"
    if label == "RECONSIDER":
        return f"{label} (n_days={m['n_days']}, EV-cons {m['ev_conservative_c']:+.2f}c -- disagrees with backtest, re-audit)"
    return f"{label} (n_days={m['n_days']}, EV-opt {m['ev_optimistic_c']:+.2f}c, confirms backtest refutation)"


if __name__ == "__main__":
    main()
