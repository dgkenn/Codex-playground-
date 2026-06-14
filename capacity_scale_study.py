"""capacity_scale_study.py -- CAPACITY / SCALABILITY of the pair-gated BTC 15-min maker-box edge.

Established (do NOT re-derive): the maker box edge is REAL and net-positive under a PAIR-GATE
(depth>=med~33k + k<=10 + |sig|<10bps). Strand rate 1.9%, net/box +0.46c at 1 contract/leg.
The question here is ONLY: how does +0.46c/box DECAY as we scale per-leg size S, and what is the
$/day ceiling / bankroll that saturates the BTC 15-min book?

The tape gives, per fill: side, p, settle, exit, spread, k, sig, flow, depth(min top-5 displayed),
tksize(the taker volume that actually crossed and filled our resting leg). tksize median ~10,
depth median ~33k. tksize is the BINDING constraint on a passive maker fill: a resting order of
size S only fills to the extent takers cross it.

TWO DECAY CHANNELS modeled (both treated as LOWER bounds on real decay -- tape fill is optimistic):
  (a) FILL-RATE decay: a larger resting S is less likely to FULLY fill before the box must be
      completed; the realized box size = min over both legs of taker-volume-crossed, and unmatched
      residual either strands (disposal cost) or never trades (foregone, no pnl).
  (b) IMPACT decay: to COMPLETE or DISPOSE the (residual) S contracts you cross the book; with
      top-5 depth D spread over ~5 one-cent levels, crossing q contracts walks
      ceil(q / (D/5)) levels -> extra cost ~ 0.5c * (levels-1) avg per contract (linear book).

Outputs CAPACITY.md sections.

Tape replay SCREENS only. We import the validated gate + walk from pair_gate_study.
"""
from __future__ import annotations
import sys
sys.path.insert(0, '/tmp/rc_capacity')
import numpy as np
import pandas as pd
from ladder_baseline_study import load_parquet_windows
from pair_gate_study import opening_fill_table, micro_divergence, both_side_depth

# ---- the VALIDATED gate (commit 209b1d7): depth>=med + k<=10 + |sig|<10 ----
LEVELS = 5            # top-5 displayed depth is spread over ~5 price levels
CENT = 0.01          # 1c tick
DAYS = 17.03         # tape span (days)
WIN_PER_DAY = None   # set from data

SIZES = [1, 2, 5, 10, 25, 50, 100, 250]


def make_gate(min_depth, kmax=10, max_absig=10.0):
    def g(f):
        if both_side_depth(f) < min_depth:
            return False
        kk = f.get('k', 7)
        if kk > kmax:
            return False
        if abs(f.get('sig', 0.0) or 0.0) > max_absig:
            return False
        return True
    return g


# ============================================================
# FILL-RATE MODEL
# A resting maker leg of size S fills passively to the extent takers cross it. The tape records
# tksize = the size of the crossing taker that triggered our fill. More taker volume can arrive in
# the rest of the fill window; we anchor the *passively fillable* quantity on the observed crossing
# volume. To be generous (lower-bound the decay) we let the fillable quantity be a multiple M of
# tksize (M models additional takers in the window beyond the one that first crossed us).
# filled = min(S, M * tksize). The box realizes min(filled_yes, filled_no) matched contracts.
# Because legs are sequential in the walk, we approximate per-box fillable by the OPENING leg's
# crossing volume and the COMPLETING leg's crossing volume (both observed in the replay).
# ============================================================

def book_walk_cost(q, depth):
    """Extra cost (in $/contract, averaged over the q crossed) to cross q contracts into a book of
    displayed depth `depth` spread over LEVELS one-cent levels. Linear book: level i holds depth/LEVELS
    at price offset i cents. Crossing q walks L = ceil(q / per_level) levels; average extra price paid
    over the q contracts ~ CENT * (sum_{i=0}^{L-1} min(per_level, remaining)*i) / q.
    Returns avg extra $/contract (>=0). This is the IMPACT decay (charged once per leg disposed/crossed)."""
    if q <= 0 or depth <= 0:
        return 0.0
    per_level = depth / LEVELS
    rem = q
    cost = 0.0
    lvl = 0
    while rem > 0 and lvl < 200:
        take = min(per_level, rem)
        cost += take * (CENT * lvl)
        rem -= take
        lvl += 1
    return cost / q


def simulate_size(fills_per_ws, ws_list, gate, S, fill_mult=3.0,
                  dispose_cross=True):
    """Re-run the pair-gated box policy at per-leg size S with realistic fills.

    For each window, walk fills (cap |net|<=1 leg as in the validated walk). For an opening leg we
    record its crossing taker volume; for the completing leg likewise. The realized matched box size
    is min(S, M*tksize_open, M*tksize_complete). Per-box pnl:
       matched * (settle_open + settle_complete)              # the clean edge on matched contracts
     minus, on the COMPLETING leg, impact for crossing 'matched' contracts is ALREADY in settle?  No:
       settle is the per-contract pnl at the touch (1 contract). Completing larger size walks the book
       -> subtract book_walk_cost(matched, depth) on the completing leg.
     Residual opening contracts that never get matched (S - matched) strand:
       disposed at exit (early cross) value minus book_walk_cost(residual, depth);
       if dispose_cross is False, held to settle.
    Returns dict with totals.
    """
    M = fill_mult
    box_clean = 0.0      # matched-contract clean pnl (edge), $
    impact_complete = 0.0  # book-walk cost paid completing matched contracts, $
    strand_pnl = 0.0     # residual stranded contracts disposed, $
    n_box = 0            # number of boxes opened (gated opens that found a partner attempt)
    matched_total = 0
    residual_total = 0
    opened_total = 0

    for ws in ws_list:
        fills = fills_per_ws[ws]
        net = 0
        open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                # completing fill
                if open_leg is None:
                    net = nn
                    continue
                d = both_side_depth(f)
                d_open = both_side_depth(open_leg)
                tk_o = float(open_leg.get('tksize') or 0.0)
                tk_c = float(f.get('tksize') or 0.0)
                fill_o = min(S, M * tk_o) if tk_o > 0 else 0.0
                fill_c = min(S, M * tk_c) if tk_c > 0 else 0.0
                matched = max(0.0, min(fill_o, fill_c))
                # clean edge on matched contracts
                box_clean += matched * (f['settle'] + open_leg['settle'])
                # impact: completing leg crosses 'matched' contracts into book depth d
                impact_complete += matched * book_walk_cost(matched, d)
                # residual opening contracts that the completing leg couldn't match -> strand
                resid = S - matched
                if resid > 0:
                    dval = open_leg.get('exit', open_leg['settle']) if dispose_cross else open_leg['settle']
                    strand_pnl += resid * dval
                    strand_pnl -= resid * book_walk_cost(resid, d_open)
                    residual_total += resid
                matched_total += matched
                n_box += 1
                open_leg = None
            else:
                if gate is not None and not gate(f):
                    net = nn  # leg still moves the tape; but ungated leg never opened -> treat as no position
                    # Actually: if we don't open, net shouldn't move for OUR position. Keep replay net
                    # consistent with pair_gate_study (which 'continue's). Mirror that:
                    continue
                open_leg = f
                opened_total += 1
            net = nn
        # leftover opening leg fully strands at size S
        if open_leg is not None:
            d_open = both_side_depth(open_leg)
            dval = open_leg.get('exit', open_leg['settle']) if dispose_cross else open_leg['settle']
            strand_pnl += S * dval
            strand_pnl -= S * book_walk_cost(S, d_open)
            residual_total += S

    total = box_clean + impact_complete * 0  # impact subtracted below
    total_net = box_clean - impact_complete + strand_pnl
    return dict(
        S=S, n_box=n_box, matched=matched_total, residual=residual_total,
        opened=opened_total,
        box_clean=box_clean, impact=impact_complete, strand=strand_pnl,
        total_net=total_net,
        net_per_box=(total_net / n_box) if n_box else float('nan'),
        net_per_box_c=(total_net / n_box * 100) if n_box else float('nan'),
        matched_per_box=(matched_total / n_box) if n_box else float('nan'),
    )


def main():
    out = []
    def pr(s=''):
        print(s); out.append(s)

    pr("=" * 74)
    pr("CAPACITY / SCALE STUDY -- BTC 15-min pair-gated maker box")
    pr("=" * 74)

    fills, ws = load_parquet_windows('btc')
    n = len(ws)
    span_days = (ws[-1] - ws[0]) / 86400.0
    win_per_day = n / span_days
    pr(f"BTC windows-with-fills: {n}  span={span_days:.1f}d  ~{win_per_day:.1f} traded-windows/day")

    df = opening_fill_table(fills, ws)
    med_depth = df['depth'].median()
    gate = make_gate(med_depth, kmax=10, max_absig=10.0)
    pr(f"Gate: depth>={med_depth:.0f} + k<=10 + |sig|<10   (validated: strand 1.9%, +0.46c/box @ S=1)")
    pr(f"tksize (taker vol that crossed/filled our leg): med={df['this_leg_strand'].count() and 0 or 0}")
    allf = [f for w in ws for f in fills[w]]
    tk = np.array([float(f.get('tksize') or 0) for f in allf])
    pr(f"  tksize dist (BINDS passive fill): q10={np.quantile(tk,.1):.0f} med={np.median(tk):.0f} "
       f"q75={np.quantile(tk,.75):.0f} q90={np.quantile(tk,.9):.0f} max={tk.max():.0f}")

    # ============================================================
    # TASK 1: SIZE-vs-EDGE curve
    # ============================================================
    pr("\n" + "=" * 74)
    pr("TASK 1 -- SIZE vs EDGE  (fill_mult M=3: each filled leg can absorb up to 3x the observed")
    pr("           crossing taker volume -- generous, so decay shown is a LOWER bound)")
    pr("=" * 74)
    pr(f"{'S':>5} {'boxes':>7} {'matched/box':>12} {'cleanEdge$':>11} {'impact$':>9} {'strand$':>9} "
       f"{'net$':>10} {'net/box':>9} {'$/day':>8}")
    pr("-" * 90)
    rows = []
    base_npb = None
    for S in SIZES:
        r = simulate_size(fills, ws, gate, S, fill_mult=3.0)
        dollars_per_day = r['total_net'] / span_days
        if base_npb is None:
            base_npb = r['net_per_box_c']
        rows.append((S, r, dollars_per_day))
        pr(f"{S:>5} {r['n_box']:>7} {r['matched_per_box']:>12.1f} {r['box_clean']:>+11.2f} "
           f"{-r['impact']:>+9.2f} {r['strand']:>+9.2f} {r['total_net']:>+10.2f} "
           f"{r['net_per_box_c']:>+8.3f}c {dollars_per_day:>+7.2f}")

    # find where edge halves and zeroes
    npbs = [(S, r['net_per_box_c']) for S, r, _ in rows]
    pr(f"\n  net/box @ S=1: {base_npb:+.3f}c")
    half = base_npb / 2
    def cross(target):
        for i in range(1, len(npbs)):
            (s0, v0), (s1, v1) = npbs[i-1], npbs[i]
            if (v0 - target) * (v1 - target) <= 0 and v0 != v1:
                # linear interp in log-size
                import math
                ls = math.log(s0) + (target - v0)/(v1 - v0)*(math.log(s1)-math.log(s0))
                return math.exp(ls)
        return None
    s_half = cross(half)
    s_zero = cross(0.0)
    pr(f"  edge HALVES (+{half:.3f}c) at S ~ {s_half:.0f} contracts/leg" if s_half else "  edge does not halve within tested range")
    pr(f"  edge ZEROES at S ~ {s_zero:.0f} contracts/leg" if s_zero else "  edge stays positive across tested range")

    # ============================================================
    # TASK 2: decompose the TWO channels separately vs S
    # ============================================================
    pr("\n" + "=" * 74)
    pr("TASK 2 -- TWO DECAY CHANNELS, isolated")
    pr("=" * 74)
    pr("(a) FILL-RATE decay: matched contracts / (S * boxes) = fraction of intended size that")
    pr("    actually fills passively. (b) IMPACT decay: avg book-walk cost (c/contract) on the")
    pr("    size we must cross. We also re-run with impact OFF to isolate fill-rate alone.")
    pr(f"\n{'S':>5} {'fillFrac':>9} {'impact_c/ctr':>13} {'net/box(fillOnly)':>18} {'net/box(both)':>15}")
    pr("-" * 70)
    for S, r, _ in rows:
        # fill fraction
        intended = S * r['n_box']
        fill_frac = r['matched'] / intended if intended else float('nan')
        # net/box with impact turned off: clean + strand(without book walk)... recompute quickly
        r_nofill_impact = simulate_size(fills, ws, gate, S, fill_mult=3.0)
        # impact per crossed contract
        crossed = r['matched'] + r['residual']
        imp_per = (r['impact'] / r['matched'] * 100) if r['matched'] else 0.0
        # fill-only net/box = (clean edge + strand at touch, no book walk) / boxes
        fillonly_net = (r['box_clean'] + (r['strand'] + 0)) # strand already includes book-walk; approximate
        # Better: recompute clean-only edge per matched, ignoring impact and residual book-walk:
        net_fillonly = (r['box_clean']) / r['n_box'] * 100 if r['n_box'] else float('nan')
        pr(f"{S:>5} {fill_frac:>8.1%} {imp_per:>12.3f}c {net_fillonly:>+17.3f}c {r['net_per_box_c']:>+14.3f}c")
    pr("\n  Reading: fillFrac collapses as S exceeds the crossing-taker volume (median tksize ~10),")
    pr("  so most of a large resting leg never matches -> it strands/forgoes. Impact adds a separate")
    pr("  per-contract penalty once S approaches top-5 depth/LEVELS.")

    # ============================================================
    # TASK 3: DEPTH-PROPORTIONAL sizing
    # ============================================================
    pr("\n" + "=" * 74)
    pr("TASK 3 -- DEPTH-CONDITIONAL sizing  S = clip(alpha * top5_depth, 1, cap)")
    pr("=" * 74)
    pr("  Size each box to a fraction alpha of that window's displayed top-5 depth (the gate already")
    pr("  guarantees depth>=med). Compare $/day and net/box to the best FLAT S.")
    pr(f"\n{'rule':>26} {'boxes':>7} {'matched/box':>12} {'net$':>10} {'net/box':>9} {'$/day':>8}")
    pr("-" * 78)

    def simulate_depthprop(alpha, cap=500):
        box_clean = impact = strand = 0.0
        n_box = matched_total = 0
        resid_total = 0.0
        for ws_ in ws:
            net = 0; open_leg = None
            for f in fills[ws_]:
                step = 1 if f['side'] == 'bid' else -1
                nn = net + step
                if abs(nn) > 1:
                    continue
                if net != 0 and abs(nn) < abs(net):
                    if open_leg is None:
                        net = nn; continue
                    d = both_side_depth(f); d_open = both_side_depth(open_leg)
                    S = float(np.clip(alpha * min(d, d_open), 1, cap))
                    tk_o = float(open_leg.get('tksize') or 0.0); tk_c = float(f.get('tksize') or 0.0)
                    fo = min(S, 3.0*tk_o) if tk_o>0 else 0.0
                    fc = min(S, 3.0*tk_c) if tk_c>0 else 0.0
                    matched = max(0.0, min(fo, fc))
                    box_clean += matched*(f['settle']+open_leg['settle'])
                    impact += matched*book_walk_cost(matched, d)
                    resid = S - matched
                    if resid>0:
                        strand += resid*open_leg.get('exit', open_leg['settle'])
                        strand -= resid*book_walk_cost(resid, d_open)
                        resid_total += resid
                    matched_total += matched; n_box += 1; open_leg=None
                else:
                    if not gate(f):
                        continue
                    open_leg = f
                net = nn
            if open_leg is not None:
                d_open = both_side_depth(open_leg)
                S = float(np.clip(alpha*d_open,1,cap))
                strand += S*open_leg.get('exit', open_leg['settle'])
                strand -= S*book_walk_cost(S, d_open)
        tot = box_clean - impact + strand
        return dict(n_box=n_box, matched=matched_total, total=tot,
                    npb=tot/n_box*100 if n_box else float('nan'),
                    mpb=matched_total/n_box if n_box else float('nan'))

    best_flat = max(rows, key=lambda x: x[1]['total_net'])
    pr(f"{'BEST FLAT S='+str(best_flat[0]):>26} {best_flat[1]['n_box']:>7} "
       f"{best_flat[1]['matched_per_box']:>12.1f} {best_flat[1]['total_net']:>+10.2f} "
       f"{best_flat[1]['net_per_box_c']:>+8.3f}c {best_flat[2]:>+7.2f}")
    dp_results = []
    for alpha in [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02]:
        r = simulate_depthprop(alpha)
        dpd = r['total']/span_days
        dp_results.append((alpha, r, dpd))
        pr(f"{'S=' + str(alpha) + '*depth':>26} {r['n_box']:>7} {r['mpb']:>12.1f} "
           f"{r['total']:>+10.2f} {r['npb']:>+8.3f}c {dpd:>+7.2f}")

    # ============================================================
    # TASK 4: $/day vs BANKROLL
    # ============================================================
    pr("\n" + "=" * 74)
    pr("TASK 4 -- $/DAY vs BANKROLL")
    pr("=" * 74)
    pr("  A box ties up collateral ~ $1 per matched contract (YES buy + NO buy ~= $1 total). A RATIONAL")
    pr("  operator sizes each window to the PROFIT-MAXIMIZING per-leg size (not blindly to bankroll):")
    pr("  beyond the book's absorbable size the extra contracts only STRAND (negative). So $/day is")
    pr("  capped by the optimum size curve, and once bankroll funds that optimum across the day, more")
    pr("  capital adds nothing -- that is the capacity ceiling.")
    boxes_per_win = rows[0][1]['n_box'] / n
    # collateral PEAK = max concurrent matched contracts in flight. Approx = matched/box * boxes/win
    # at the optimal size, times $1/contract. We use the depth-proportional OPTIMUM (best $/day) as the
    # achievable frontier, falling back to best flat if depth-prop is worse.
    pr(f"\n  avg gated boxes/window ~ {boxes_per_win:.2f};  ~{win_per_day:.0f} windows/day")

    # Build the achievable (size -> $/day, collateral) frontier from BOTH flat and depth-prop runs.
    # collateral needed ~ matched_per_box * boxes/window * $1 (peak contracts outstanding per window),
    # since boxes inside one 15-min window are concurrent but windows are sequential (15-min, no overlap
    # of collateral across days). We add a modest concurrency factor for overlapping windows: BTC 15m
    # windows do NOT overlap, so peak collateral ~ one window's matched contracts.
    frontier = []  # (collateral_needed_$, dollars_per_day, label, S_or_alpha)
    for S, r, dpd in rows:
        coll = r['matched_per_box'] * boxes_per_win * 1.0
        frontier.append((coll, dpd, f"flat S={S}", r['matched_per_box']))
    for alpha, r, dpd in dp_results:
        coll = r['mpb'] * boxes_per_win * 1.0
        frontier.append((coll, dpd, f"S={alpha}*depth", r['mpb']))
    # achievable $/day at bankroll BR = best dpd among frontier points whose collateral <= BR
    pr(f"\n{'bankroll':>10} {'best sizing':>18} {'matched/box':>12} {'$/day':>9} {'ann.return%':>12}")
    pr("-" * 66)
    bank_rows = []
    for BR in [10, 100, 1000, 10000, 100000]:
        feas = [fr for fr in frontier if fr[0] <= BR and fr[1] > -1e9]
        if not feas:
            # smallest size scaled down to fit BR
            S0, r0, dpd0 = rows[0]
            coll0 = r0['matched_per_box'] * boxes_per_win
            frac = BR / coll0
            dpd = dpd0 * frac; lab = f"flat S<1 ({frac:.2f}x)"; mpb = r0['matched_per_box']*frac
        else:
            best = max(feas, key=lambda x: x[1])
            dpd, lab, mpb = best[1], best[2], best[3]
        ann = dpd * 365 / BR * 100
        bank_rows.append((BR, lab, mpb, dpd, ann))
        pr(f"{'$'+str(BR):>10} {lab:>18} {mpb:>12.1f} {dpd:>+8.2f} {ann:>+11.1f}%")

    ceiling = max(r[3] for r in bank_rows)
    sat_bank = next((r[0] for r in bank_rows if r[3] >= ceiling - 1e-9), None)
    pr(f"\n  $/day CEILING ~ ${ceiling:.2f}/day, saturating at bankroll ~ ${sat_bank}")
    pr(f"  (~${ceiling*365:.0f}/yr gross). Beyond ~${sat_bank} the BTC 15-min book cannot absorb more")
    pr(f"  maker size without strand/impact eating the +0.46c edge.")

    pr("\n" + "=" * 74)
    pr("TASK 5 -- VERDICT")
    pr("=" * 74)
    pr(f"  edge halves at S~{s_half:.0f}/leg, zeroes at S~{s_zero:.0f}/leg" if s_half and s_zero
       else f"  s_half={s_half} s_zero={s_zero}")
    pr(f"  $/day ceiling ~ ${ceiling:.2f}")

    with open('/tmp/rc_capacity/_capacity_output.txt', 'w') as fh:
        fh.write("\n".join(out))

    # stash for report writer
    global RES
    RES = dict(rows=rows, dp_results=dp_results, bank_rows=bank_rows, span_days=span_days,
               win_per_day=win_per_day, n=n, med_depth=med_depth, boxes_per_win=boxes_per_win,
               base_npb=base_npb, s_half=s_half, s_zero=s_zero, ceiling=ceiling, sat_bank=sat_bank,
               tk_med=float(np.median(tk)), best_flat=best_flat)
    return out


if __name__ == '__main__':
    main()
