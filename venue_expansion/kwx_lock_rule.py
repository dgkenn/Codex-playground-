#!/usr/bin/env python3
"""kwx_lock_rule.py -- read-only, backtest-only extraction of the DEPLOYED lock rule from kwx_runner.py.

WHY THIS FILE EXISTS: kwx_runner.py (the live detection+decision loop) is a live-path file that, per
venue_expansion/GROUNDING.md, "live[s] on another branch anyway -- this branch is research-only" and is
off-limits to touch. It is genuinely absent from this branch's working tree (confirmed: `git ls-tree` on
this branch has no kwx_runner.py; it exists on origin/batch/pmkt-verdict etc.). ref/pmkt_final_verdict.py
does `import kwx_runner as R` and calls exactly two of its functions -- `R.sustained_extreme` and
`R.locked_orders` -- both pure, stateless, deterministic backtest math with no execution/exchange/feed-
credential side effects. Rather than either (a) copying the ENTIRE live runner (including KalshiExec sizing,
Telegram wiring, feed-credential probing) onto this research branch, which would violate the "never touch
live-path files" / off-limits instruction in spirit even if just for import, or (b) re-deriving the lock
math from prose and risking a silent behavioral drift, this file extracts VERBATIM (byte-identical function
bodies, unmodified) just those two functions plus the constants they read, from the EXACT commit that was
paired with pmkt_final_verdict.py when it was authored:

    commit bd90504 "Polymarket phase 2: whitelist false-lock rate + loss-inclusive EV -> STILL-BLOCKED
    verdict" (origin/batch/pmkt-verdict), file kwx_runner.py, lines 374-423 (sustained_extreme) and
    463-486 (locked_orders), plus the constants block lines 61-67.

No live/execution code (sizing, Kalshi API calls, Telegram, feed classes) is reproduced here -- only the
deterministic glitch-filter + sustain-3 + margin lock math the backtest actually calls. This is the SAME
rule Track A's pre-registered bars point at ("deployed sustain-3 margin-cleared extreme rule"), reused
without modification.
"""
import datetime as dt

# ---- frozen strategy params (verbatim from kwx_runner.py @ bd90504, lines 61-67) ----
MARGIN_F = 1.0          # base: observed extreme must clear strike by this many degF (Track A/Tier-1: best)
SUSTAIN_MIN = 3         # sustained this many minutes -- glitch-robust (Tier-1 S2: sustain=3 reconfirmed;
                        # sustain=1 turns 13.7% of fires into glitch losses vs 0.35% at sustain=3)
SUSTAIN_MAX_GAP_MIN = 75  # max gap between adjacent obs inside a sustain window (bridges hourly METAR;
                          # never bridges a multi-hour feed outage)
MAX_PAY_CENTS = 98      # never pay above this (skip dead-on-arrival fires -- ~63% of raw fires have no gap)
GLITCH_HI_F, GLITCH_LO_F = 130.0, -60.0


# ---------------- sustained-cross logic (glitch-robust) -- verbatim from kwx_runner.py @ bd90504 ----------
def sustained_extreme(obs, kind):
    """Given [(iso_ts, temp_f)...] ascending, return the glitch-filtered running extreme that has been
    SUSTAINED >= SUSTAIN_MIN minutes -- the validated Track-B "glitch_sustain3" rule
    (phase2_trackB_tail.sustained_max_k): for a max, the largest threshold T such that some window of
    consecutive surviving readings spanning >= SUSTAIN_MIN-1 minutes stays entirely >= T. On the study's
    1-min data that is exactly 3 consecutive minutes; on the live 5-min/hourly feeds the smallest
    qualifying window (two adjacent readings) spans >= 5 min, i.e. coarser feeds are strictly MORE
    conservative than the validated rule, never less. Adjacent readings inside a window may be at most
    SUSTAIN_MAX_GAP_MIN apart (bridges hourly METAR cadence, never a multi-hour outage).

    Returns None when no window qualifies yet (single reading so far, sparse day, unparseable
    timestamps). Callers MUST treat None as NO SIGNAL -- falling back to the raw running extreme would
    silently reinstate sustain=1, the 13.7%-glitch-loss rule the tail study rejected."""
    clean = []
    prev = None
    for ts, f in obs:
        if f is None or f > GLITCH_HI_F or f < GLITCH_LO_F:
            continue
        if prev is not None and abs(f - prev) > 8.0:
            # potential 1-min glitch: require it to persist by not trusting a single jump; skip this point
            # (a true climb shows consecutive steps; a spike reverts). Conservative: skip the jump point.
            prev = f
            continue
        prev = f
        try:
            t = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        clean.append((t, f))
    if not clean:
        return None
    span_need = dt.timedelta(minutes=max(0, SUSTAIN_MIN - 1))
    max_gap = dt.timedelta(minutes=SUSTAIN_MAX_GAP_MIN)
    sign = 1.0 if kind == "max" else -1.0
    best = None
    for j in range(len(clean)):
        tj = clean[j][0]
        wmin = sign * clean[j][1]
        i = j
        # grow the window leftward (gap-connected) until it spans SUSTAIN_MIN-1 minutes; the minimal
        # qualifying window ending at j maximizes the window-min, so stop as soon as the span is met.
        while tj - clean[i][0] < span_need and i > 0 and clean[i][0] - clean[i - 1][0] <= max_gap:
            i -= 1
            v = sign * clean[i][1]
            if v < wmin:
                wmin = v
        if tj - clean[i][0] >= span_need and (best is None or wmin > best):
            best = wmin
    return None if best is None else sign * best


# ---------------- lock logic (which rung side locks, given the observed extreme) -- verbatim -------------
def locked_orders(rungs, extreme_f, kind, margin=MARGIN_F):
    """Return list of (ticker, side, buy_price_cap_c, cushion_f) for rungs now mechanically locked by the
    observed extreme (with `margin`, which may be raised per-station for high-disagreement stations). HIGH/max:
    floor-only rung locks YES once max>floor+margin; any capped rung locks NO once max>cap+margin.
    LOW/min mirrors with the running min. cushion_f = |obs - the relevant strike| (degF the obs cleared the
    strike by) -> feeds the conviction upsizing; larger cushion = more headroom vs a late CLI revision."""
    orders = []
    for r in rungs:
        floor, cap = r["floor"], r["cap"]
        if kind == "max":
            if cap is not None and extreme_f > cap + margin:
                if r["no_ask_c"] and r["no_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "no", r["no_ask_c"], extreme_f - cap))
            elif cap is None and floor is not None and extreme_f > floor + margin:
                if r["yes_ask_c"] and r["yes_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "yes", r["yes_ask_c"], extreme_f - floor))
        else:  # min
            if floor is not None and extreme_f < floor - margin:
                if r["no_ask_c"] and r["no_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "no", r["no_ask_c"], floor - extreme_f))
            elif floor is None and cap is not None and extreme_f < cap - margin:
                if r["yes_ask_c"] and r["yes_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "yes", r["yes_ask_c"], cap - extreme_f))
    return orders
