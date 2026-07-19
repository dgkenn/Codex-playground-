#!/usr/bin/env python3
"""wx_subdegree_cushion.py -- is the optimal cushion SUB-degree? (settlement is integer, obs is continuous)

Kalshi temp strikes are whole degF and the NWS CLI settles as a whole INTEGER degF (verified: 13.9k CLI values,
all integer). So market ">K" settles YES iff CLI_high >= K+1, i.e. the TRUE max >= K+0.5 (that's the value that
rounds up to K+1). Our observed running max is CONTINUOUS (tenths). The live rule fires at a WHOLE-degree
margin (obs > K+1), which is ~0.5degF later than the real settlement boundary at K+0.5 -- potentially leaving
a band of already-won fires on the table. This measures the lock-failure rate as a function of the CONTINUOUS
cushion delta = obs_sustained_max - K, from the multi-year Track B cache, to find the finest cushion that is
still safe (and thus how much earlier than margin=1 we could fire).

For each station-day (CLI integer C, deployed obs = sustain3_max V) and each near-money integer strike K in
[C-4 .. C+3]: a YES on ">K" LOCK-FAILS iff C <= K. Bin fires by delta=V-K (0.1degF bins) and report the
lock-failure rate per bin + cumulative (fire iff delta >= t). The threshold t where cumulative lock-fail hits
our tolerance (~the 0.35% we already accept at margin=1) is the true minimum cushion.
"""
import json, glob, os
from collections import defaultdict

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tailrisk_cache")
KRANGE = range(-4, 4)          # near-money integer strikes around C
BINW = 0.1


def load():
    """Yield (delta, lockfail_bool) for every (station-day, near-money strike) where obs cleared K (delta>0)."""
    out = []
    for fp in glob.glob(os.path.join(CACHE, "daily_*.json")):
        for rec in json.load(open(fp)):
            C = rec.get("cli_high"); V = rec.get("sustain3_max")
            if C is None or V is None:
                continue
            try:
                C = int(round(C))
            except Exception:
                continue
            for off in KRANGE:
                K = C + off
                delta = V - K
                if delta <= 0:            # obs didn't clear K at all -> the rule never fires here
                    continue
                out.append((delta, K >= C))   # lock-fail iff strike settles NO (C <= K)
    return out


def _obs_precision():
    """Are the stored observations continuous (tenths) or quantized to whole degF? Decides if sub-degree is
    even measurable."""
    frac = 0
    tot = 0
    for fp in glob.glob(os.path.join(CACHE, "daily_*.json")):
        for rec in json.load(open(fp)):
            v = rec.get("sustain3_max")
            if v is None:
                continue
            tot += 1
            if abs(v - round(v)) > 1e-6:
                frac += 1
    return frac, tot


def main():
    fr, tot = _obs_precision()
    print("OBS PRECISION CHECK: of {} observed maxima, {} have a fractional part ({:.1f}%).".format(
        tot, fr, 100.0 * fr / max(tot, 1)))
    if fr == 0:
        print(">>> Observations are WHOLE-degree (ASOS/METAR tmpf rounds to integer degF), and CLI settlement is\n"
              "    also integer. So the cushion is QUANTIZED to 1 degF on BOTH sides -- there is no measurable\n"
              "    0.5/0.2/0.1 cushion in this data; the finest resolvable (and optimal) cushion is 1 degF = margin=1.\n"
              "    A sub-degree cushion is only even definable with a TENTHS-precision feed (Synoptic HF-ASOS /\n"
              "    raw DSI-6405 1-min); and since settlement stays integer, its only payoff would be firing ~0.5 degF\n"
              "    earlier at the K+0.5 rounding boundary -- a marginal, Synoptic-gated refinement, not a live knob now.\n")
    data = load()
    n = len(data)
    print(f"delta-grid below is therefore quantized to whole degF ({n} fire-eligible station-day x strike points):\n")

    # cumulative: if we require delta >= t, what's the lock-fail rate + how many fires remain?
    thresholds = [round(0.1 * i, 1) for i in range(0, 31)]   # 0.0 .. 3.0
    base_fires = sum(1 for d, _ in data if d >= 1.0)          # current rule: margin=1 (delta>=1.0)
    print(f"{'cushion>=':>10}{'fires':>8}{'vs m=1':>8}{'lockfail%':>11}{'per-100-extra-fires: fails':>28}")
    prev_fires, prev_fail = None, None
    for t in thresholds:
        sub = [lf for d, lf in data if d >= t]
        nf = len(sub)
        if nf == 0:
            continue
        fr = 100.0 * sum(sub) / nf
        rel = nf / base_fires if base_fires else float("nan")
        # marginal quality of the fires between this threshold and the next-higher 0.1 band
        band = [lf for d, lf in data if t <= d < t + BINW]
        btxt = f"{100*sum(band)/len(band):.1f}% of {len(band)}" if band else "-"
        star = "  <- current (margin=1)" if abs(t - 1.0) < 1e-9 else ("  <- settle boundary" if abs(t - 0.5) < 1e-9 else "")
        print(f"{t:>9.1f}F{nf:>8}{rel:>7.2f}x{fr:>10.2f}%{btxt:>28}{star}")

    # headline: the finest cushion whose cumulative lock-fail stays <= the margin=1 rate, and the EV upside
    m1 = [lf for d, lf in data if d >= 1.0]
    m1_fail = 100.0 * sum(m1) / len(m1)
    print(f"\nmargin=1 (delta>=1.0F) lock-fail = {m1_fail:.2f}% on {len(m1)} fires (the current bar).")
    for t in [round(0.1 * i, 1) for i in range(5, 11)]:
        sub = [lf for d, lf in data if d >= t]
        fr = 100.0 * sum(sub) / len(sub)
        extra = len(sub) / len(m1) - 1.0
        print(f"  cushion>={t:.1f}F: lock-fail {fr:.2f}%  |  {100*extra:+.0f}% fires vs margin=1"
              + ("   <= m1 bar (SAFE to lower here)" if fr <= m1_fail + 0.05 else ""))
    print("\nread: settlement boundary is K+0.5, so cushion 0.5-0.9F fires EARLIER than margin=1. If the lock-fail "
          "at, say, 0.7F stays near the margin=1 rate, lowering the live margin captures those extra fires (more EV) "
          "at ~the same risk. Note obs (sustain3) reads ~0.9F LOW vs CLI on average, which is why a sub-0.5 nominal "
          "cushion can still be safe -- the observed value understates the true max that the CLI rounds from.")


if __name__ == "__main__":
    main()
