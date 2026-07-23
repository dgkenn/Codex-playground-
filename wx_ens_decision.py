#!/usr/bin/env python3
"""wx_ens_decision.py -- DECISION LAYER for the 51-member ECMWF ensemble forward logger
(wx_ens_forward.py). Style/structure mirrors wx_earlylock_decision.py.

Reads ONLY wx_ens_settled.jsonl (paper, no orders, no credentials) and prints a verdict:

  ACTIVATE          -- the PRE-REGISTERED bar (frozen before any settled data existed) is cleared.
  ACCRUING(n/30)     -- not enough distinct trading days yet either way; reports an honest ETA at the
                        observed live candidate rate.
  KILL              -- enough days accrued that the bar is decisively NOT clearing (EV<=0 net of fee, or
                        the ensemble is no more calibrated than Kalshi's own price -- see Brier check).

PRE-REGISTERED ACTIVATION BAR (frozen in wx_ens_forward.py's EDGE_THR derivation and here, BEFORE reading
any settled row -- never moved after seeing results, per CLAUDE.md research discipline):
  day-clustered t   >= T_BAR  (3.0)   -- one-sample t-test on per-day mean pnl, not one lucky day
  EV/contract        >  0             -- net of the Kalshi taker fee (CLAUDE.md ceil(7*p*(1-p))/100 rule),
                                          already baked into each settled row's `pnl` by wx_ens_forward.settle
  n distinct days    >= N_DAYS_BAR (30)   -- enough independent trading days to trust an average
  ensemble Brier     <  Kalshi Brier   -- the ensemble's P(yes) must be BETTER CALIBRATED than the market's
                                          own implied probability at snapshot time, not just directionally
                                          profitable by luck; this is the sleeve's raison d'etre (a genuinely
                                          informative 51-member distribution should out-calibrate the market)

FEE TREATMENT: `pnl` in each settled row is already net of fee (computed once in wx_ens_forward.settle at
the LOGGED entry price); this module only aggregates it, exactly as wx_earlylock_decision does.

BRIER SCORE: for each settled row, y = 1 if result=='yes' else 0.
  ensemble_brier_term = (ensemble_P - y)^2
  kalshi_p_yes = market-implied P(yes) at snapshot time, built from whichever raw ask(s) were captured:
    both present  -> mean(yes_ask_c/100, 1 - no_ask_c/100)
    yes_ask only  -> yes_ask_c/100
    no_ask only   -> 1 - no_ask_c/100
  kalshi_brier_term = (kalshi_p_yes - y)^2
Lower mean Brier = better calibrated. This is compared over the SAME settled sample (paired), so it is not
confounded by which rows happened to log a paper candidate.

NO LIVE TRADING INTEGRATION: reads wx_ens_settled.jsonl and prints a verdict only. Never places orders,
never reads credentials, never sets KWX_LIVE, never touches kwx_runner/kalshi_exec/kwx_paper_gate.

Usage:
    python wx_ens_decision.py
"""
import math
import statistics as stt
from collections import defaultdict

import wx_ens_forward as F   # reuse SETTLED/PAPER paths, EDGE_THR, _load_jsonl

# ---------------- PRE-REGISTERED bar (frozen before any settled data is read) ----------------
T_BAR = 3.0            # day-clustered t on per-day mean pnl
EV_BAR_C = 0.0          # EV/contract (cents, net of fee) must be strictly positive
N_DAYS_BAR = 30         # distinct settled trading days
N_DAYS_KILL = 30        # need at least this many distinct days before KILL is a supportable claim


def wilson_ci(k, n, z=1.96):
    """Two-sided Wilson score CI for a binomial proportion k/n -- same formula as
    wx_earlylock_decision.wilson_ci / wx_ev_concentration.wilson_ci."""
    if n <= 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def _by_day(rows):
    byday = defaultdict(list)
    for r in rows:
        byday[r["date"]].append(r)
    return byday


def day_clustered_t(rows):
    """One-sample t-test on per-day mean pnl. Returns (t, n_days); t is NaN if <2 distinct days or zero
    day-to-day variance (mirrors wx_earlylock_forward.report() / wx_earlylock_decision.day_clustered_t)."""
    byday = _by_day(rows)
    dm = [stt.mean(r["pnl"] for r in v) for v in byday.values()]
    if len(dm) > 1 and stt.stdev(dm) > 0:
        return stt.mean(dm) / (stt.stdev(dm) / math.sqrt(len(dm))), len(dm)
    return float("nan"), len(dm)


def _kalshi_p_yes(r):
    """Market-implied P(yes) at snapshot time from whichever raw ask(s) got captured. Rows logged before
    both asks were persisted fall back to the single captured side's implied probability."""
    ya, na = r.get("yes_ask_c"), r.get("no_ask_c")
    if ya and na:
        return (ya / 100.0 + (1.0 - na / 100.0)) / 2.0
    if ya:
        return ya / 100.0
    if na:
        return 1.0 - na / 100.0
    # oldest rows (pre both-ask logging): reconstruct from the single captured side.
    p = r["entry_price_c"] / 100.0
    return p if r["kalshi_side"] == "yes" else 1.0 - p


def _accrual_rate_per_day(paper_rows):
    """Observed LIVE candidate rate (paper rows/day since the first logged row), for an honest ETA --
    mirrors wx_earlylock_decision._accrual_rate_per_day."""
    if not paper_rows:
        return 0.0, 0.0, 0
    import datetime as dt
    dates = sorted(r["date"] for r in paper_rows)
    d0 = dt.date.fromisoformat(dates[0])
    d1 = dt.date.fromisoformat(dates[-1])
    span_days = max(1.0, (d1 - d0).days + 1)
    return len(paper_rows) / span_days, span_days, len(paper_rows)


def _eta_days(n_days, rate_per_day):
    """Honest ETA in CALENDAR days to reach N_DAYS_BAR distinct settled days. Deliberately NOT
    (bar-n_days)/rate -- rate is in candidates/day, not days/day, so that ratio has the wrong units (a
    units bug present in an earlier draft of this module). Instead: once the snapshot+settle cron runs
    daily, each calendar day adds at most one distinct settled day, and adds one FOR SURE as long as at
    least one candidate from that day resolves -- which the observed candidate rate (rate_per_day) makes
    likely whenever it's > 0. So the honest estimate is simply the number of remaining calendar days,
    conditioned on the candidate rate being nonzero (else unknown -- nothing is accruing at all)."""
    if n_days >= N_DAYS_BAR:
        return 0.0
    if rate_per_day <= 0:
        return float("inf")
    return float(N_DAYS_BAR - n_days)


def compute():
    """Never raises: missing/empty settled log -> n=0 (ACCRUING)."""
    settled = F._load_jsonl(F.SETTLED)
    paper = F._load_jsonl(F.PAPER)
    n = len(settled)
    byday = _by_day(settled)
    n_days = len(byday)
    out = {
        "n": n, "n_days": n_days, "n_paper_logged": len(paper),
        "rate_per_day": 0.0, "span_days": 0.0, "eta_days": None,
    }
    rate, span, _ = _accrual_rate_per_day(paper)
    out["rate_per_day"], out["span_days"] = rate, span
    if n == 0:
        out["eta_days"] = _eta_days(0, rate)
        return out

    wins = sum(1 for r in settled if r["won"])
    pnls = [r["pnl"] for r in settled]
    win_pt = wins / n
    win_lo, win_hi = wilson_ci(wins, n)
    ev_c = stt.mean(pnls) * 100.0
    t, _ = day_clustered_t(settled)

    ens_brier_terms, kal_brier_terms = [], []
    for r in settled:
        y = 1.0 if r.get("result") == "yes" else 0.0
        ens_brier_terms.append((r["ensemble_P"] - y) ** 2)
        kal_brier_terms.append((_kalshi_p_yes(r) - y) ** 2)
    ens_brier = stt.mean(ens_brier_terms)
    kal_brier = stt.mean(kal_brier_terms)

    bykind = defaultdict(list)
    for r in settled:
        bykind[r.get("kind", "max")].append(r)

    out.update({
        "wins": wins, "win_pt": win_pt, "win_lo": win_lo, "win_hi": win_hi,
        "ev_c": ev_c, "t": t,
        "worst_pnl_c": min(pnls) * 100.0, "best_pnl_c": max(pnls) * 100.0,
        "ens_brier": ens_brier, "kal_brier": kal_brier,
        "bykind": {k: {"n": len(v), "win": sum(1 for x in v if x["won"]) / len(v),
                        "ev_c": stt.mean(x["pnl"] for x in v) * 100.0} for k, v in bykind.items()},
    })
    out["eta_days"] = _eta_days(n_days, rate)
    return out


def verdict(m):
    n, n_days = m["n"], m["n_days"]
    if n_days >= N_DAYS_BAR and n > 0:
        t_ok = isinstance(m["t"], float) and m["t"] == m["t"] and m["t"] >= T_BAR
        ev_ok = m["ev_c"] > EV_BAR_C
        brier_ok = m["ens_brier"] < m["kal_brier"]
        if t_ok and ev_ok and brier_ok:
            return ("ACTIVATE",
                    f"bar cleared: EV/ct {m['ev_c']:+.2f}c > {EV_BAR_C:+.1f}c, day-clustered t={m['t']:.2f} "
                    f">= {T_BAR:.1f}, n_days={n_days} >= {N_DAYS_BAR}, "
                    f"ensemble Brier {m['ens_brier']:.4f} < Kalshi Brier {m['kal_brier']:.4f}")
        reasons = []
        if not ev_ok:
            reasons.append(f"EV/ct {m['ev_c']:+.2f}c does not clear {EV_BAR_C:+.1f}c")
        if not t_ok:
            t_str = f"{m['t']:.2f}" if isinstance(m["t"], float) and m["t"] == m["t"] else "NaN"
            reasons.append(f"day-clustered t={t_str} < {T_BAR:.1f}")
        if not brier_ok:
            reasons.append(f"ensemble Brier {m['ens_brier']:.4f} NOT < Kalshi Brier {m['kal_brier']:.4f} "
                            f"(ensemble is no better calibrated than the market's own price)")
        if n_days >= N_DAYS_KILL:
            return ("KILL", "bar not cleared at n_days>=" + str(N_DAYS_KILL) + ": " + "; ".join(reasons))
    eta = m.get("eta_days")
    eta_str = ("unknown -- zero live candidate rate so far" if not eta or eta == float("inf")
               else f"~{eta:.0f} days at the observed live rate ({m['rate_per_day']:.2f} candidates/day "
                    f"over {m['span_days']:.1f} days so far)")
    return ("ACCRUING", f"n_days={n_days} settled (need {N_DAYS_BAR} to ACTIVATE-or-KILL); "
                         f"{n} settled rows, {m['n_paper_logged']} paper rows logged total; "
                         f"honest ETA to n_days={N_DAYS_BAR}: {eta_str}")


def print_report(m, v):
    label, reason = v
    print("=" * 100)
    print("WX ENSEMBLE FORWARD -- DECISION LAYER (51-member ECMWF ensemble vs live Kalshi price)")
    print("=" * 100)
    print(f"  settled candidates   : {m['n']}   ({m['n_days']} distinct days)")
    print(f"  paper rows logged    : {m['n_paper_logged']} total")
    print(f"  observed candidate rate : {m['rate_per_day']:.2f}/day over {m['span_days']:.1f} days")
    if m["n"]:
        print(f"  win rate             : {m['win_pt']:.1%} pt-est   [{m['win_lo']:.1%}, {m['win_hi']:.1%}] Wilson 95% CI")
        print(f"  EV / contract        : {m['ev_c']:+.2f}c   (net of Kalshi fee)")
        print(f"  day-clustered t      : {m['t']:.2f}   (bar {T_BAR:.1f})")
        print(f"  worst / best pnl     : {m['worst_pnl_c']:+.1f}c / {m['best_pnl_c']:+.1f}c")
        print(f"  ensemble Brier       : {m['ens_brier']:.4f}   vs   Kalshi Brier {m['kal_brier']:.4f}   "
              f"({'ensemble better-calibrated' if m['ens_brier'] < m['kal_brier'] else 'NOT better-calibrated'})")
        if m.get("bykind"):
            print("  by case (HIGH=max/LOW=min):")
            for k in ("max", "min"):
                s = m["bykind"].get(k)
                if s:
                    print(f"    {k:<4} n={s['n']:<4} win={s['win']:.1%}  EV/ct={s['ev_c']:+.2f}c")
    print(f"\n  BAR (ACTIVATE): EV/ct > {EV_BAR_C:+.1f}c, day-clustered t >= {T_BAR:.1f}, "
          f"n_days >= {N_DAYS_BAR}, ensemble Brier < Kalshi Brier")
    print(f"  BAR (KILL)    : n_days >= {N_DAYS_KILL} AND the ACTIVATE bar is not cleared")
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
    """Compact summary for kwx_daily_digest.py's fail-soft digest line: `ens_forward: <verdict summary>`."""
    m = compute()
    label, reason = verdict(m)
    if label == "ACCRUING":
        return f"{label} (n_days={m['n_days']}/{N_DAYS_BAR}, {m['n_paper_logged']} logged, ETA {reason.rsplit(': ', 1)[-1]})"
    if label == "ACTIVATE":
        return f"{label} (n_days={m['n_days']}, EV/ct {m['ev_c']:+.2f}c, t={m['t']:.2f})"
    return f"{label} (n_days={m['n_days']}, EV/ct {m['ev_c']:+.2f}c, Brier ens={m['ens_brier']:.4f}/kal={m['kal_brier']:.4f})"


if __name__ == "__main__":
    main()
