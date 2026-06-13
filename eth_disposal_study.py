"""eth_disposal_study.py -- UNPAIRED-LEG DISPOSAL ladder, ETH-tuned.

The BACK HALF of the strand-handling ladder for the ETH 15-min crypto box.
A separate agent handles ETH entry-PREVENTION/PREDICTION; this script handles
DISPOSAL of an already-stranded ETH leg:

  BASELINE : how much does the unpaired leg cost ETH at the P0 hold-to-settle level,
             and what do ETH strands look like (side / slot / price region)?
  R3 COMPLETE : chase/re-quote to pair the stranded ETH leg (give sweep + force-complete-age).
  R4 MANAGE/SELL : sell the stranded ETH leg cheap (exit value); ETH-tuned price threshold sweep,
             sell-all vs sell-cheap, tox-conditioned.
  R5 HEDGE  : (a) CROSS-ASSET BTC hedge of an ETH strand -- the MIRROR of the established
                  ETH-hedges-BTC finding (R^2 18.6% / |corr| 0.43). Regress ETH-strand
                  directional P&L on concurrent BTC 15-min move; report R^2/|corr|/std-red and
                  the delta-matched hedge value.
              (b) ETH-perp delta-hedge at scale (integer-contract lumpy, $6 min).
              (c) concurrent-window coverage for the BTC hedge.
  STACK     : best disposal rungs stacked; total ETH strand-loss reduction + ETH box net.

IS = first 60% / OOS = last 40%. Backtests SCREEN; forward-validation required.
Writes ETH_DISPOSAL.md.
"""
from __future__ import annotations
import sys, bisect
sys.path.insert(0, '/tmp/eth_disposal')
import numpy as np

import ladder_baseline_study as L
from ladder_hedge_optimize import perp_hedge_value_lumpy, PERP_MIN_USD, BASE_BOX_USD, DELTA_PER_CT_USD
from box_policy_ab import hedge_unpaired, tox_p


# ============================================================
# helpers
# ============================================================

def p_yeq(f):
    return f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)

def fav_prob(f):
    py = p_yeq(f)
    return max(py, 1.0 - py)


def extract_strands(fpw, wsl):
    """Walk each window under always-pair (P0); return list of (ws, open_leg) strands."""
    out = []
    for ws in wsl:
        fills = fpw[ws]; net = 0; open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1; nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                open_leg = None
            else:
                open_leg = f
            net = nn
        if open_leg is not None:
            out.append((ws, open_leg))
    return out


def window_pnl_with_handler(fpw, wsl, handler):
    """Per-window PnL where a stranded leg is valued by handler(ws, f)->per-contract pnl.
    Paired boxes settle normally. handler=None -> hold naked (settle)."""
    pnl_arr = []; strand_arr = []
    for ws in wsl:
        fills = fpw[ws]; net = 0; pnl = 0.0; open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1; nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                pnl += f['settle'] + (open_leg['settle'] if open_leg else 0.0)
                open_leg = None
            else:
                open_leg = f
            net = nn
        stranded = open_leg is not None
        if stranded:
            pnl += handler(ws, open_leg) if handler else open_leg['settle']
        pnl_arr.append(pnl); strand_arr.append(stranded)
    return np.array(pnl_arr, float), np.array(strand_arr, bool)


def strand_pool_stats(strands, value_fn):
    """value_fn(ws,f)->per-contract value; return (mean_c, std_c, vals_array)."""
    vals = np.array([value_fn(w, f) for w, f in strands], float)
    return vals.mean() * 100, vals.std(ddof=1) * 100, vals


# ============================================================
# R3 COMPLETE -- chase-give / force-complete model
# ============================================================
# On the tape we cannot literally re-quote, but the framework gives the leg's
# `exit` value = the cost to FLATTEN at the touch ~1 min later (cross the spread).
# COMPLETE = pair the leg by giving up the spread, i.e. take the opposite leg at
# the touch. For a stranded leg, completing the box from the strand minute means
# accepting the box at the then-current prices. The economically clean proxy on
# this tape is: a fully-completed box locks ~the spread cost; the framework's
# `exit` field already encodes the flatten-at-touch P&L (sell the leg back), which
# is the MANAGE rung. For COMPLETE we model giving `give` cents of edge to force
# the pairing leg: value = settle if it would have paired, else (settle - give)
# capped at the flatten value. Because the strand pool is exactly the legs that
# did NOT pair, "prompt completion" = paying the half-spread to cross now:
#   complete_value = -spread (you give up the spread to acquire the missing leg
#   and lock the box at ~breakeven minus the give), but on a single-strike box the
#   completed box settles to (res - b_open) + (a_complete - res) = a_complete - b_open
#   = -spread_at_completion. The best proxy we HAVE is `exit` (flatten) which equals
#   the box-end value of unwinding; force-complete-from-strand-minute on BTC was
#   optimal, so we model COMPLETE as min(hold, flatten) discipline = take the better
#   of holding vs flattening, with a `give` haircut.

def complete_value(ws, f, give=0.0):
    """Force-complete the stranded leg from the strand minute by giving `give` cents of edge.
    Proxy: completing pairs the box at ~the spread cost. We model the recovered value as the
    flatten/exit value minus the chase give-up (paying to cross). This is the deployable lower
    bound: you flatten at the touch (exit) and pay `give` for the urgency."""
    ex = f.get('exit', f['settle'])
    return ex - give


# ============================================================
# R5 (a) CROSS-ASSET BTC HEDGE of an ETH strand  (the MIRROR)
# ============================================================
# Established (ETH hedges BTC): R^2 18.6%, |corr| 0.43. We now ask the SYMMETRIC
# question: does a BTC 15-min binary hedge an ETH strand?
# Rule: ETH YES-strand (bid, long ETH-up) -> buy BTC-NO (down); ETH NO-strand -> buy BTC-YES.
# The hedge instrument is the concurrent BTC 15-min window's realized direction.

def build_btc_lookup(fpw_btc, ws_btc):
    """ws -> (btc_up, btc_yes_px, spread, k_slot, spot, sset) for the concurrent BTC window."""
    out = {}
    for ws in ws_btc:
        fills = fpw_btc[ws]
        if not fills:
            continue
        f0 = fills[0]
        s0 = f0.get('spot'); ss = f0.get('sset')
        if not s0 or not ss:
            continue
        btc_up = 1 if ss >= s0 else 0
        best = min(fills, key=lambda g: abs(p_yeq(g) - 0.5))
        btc_yes_px = p_yeq(best)
        out[ws] = (btc_up, btc_yes_px, best.get('spread', 0.02), best.get('k', 7), s0, ss)
    return out


def nearest_key(ws, keys_sorted, tol=450):
    i = bisect.bisect_left(keys_sorted, ws - tol)
    best = None; bestd = tol + 1
    j = i
    while j < len(keys_sorted) and keys_sorted[j] <= ws + tol:
        d = abs(keys_sorted[j] - ws)
        if d < bestd:
            bestd = d; best = keys_sorted[j]
        j += 1
    return best


# BTC/ETH directional binary corr proxy (the delta-match coefficient). We MEASURE
# it on this tape below (the regression of ETH-strand directional P&L on BTC move),
# and use the measured |corr| as the delta-scaling coefficient.
def btc_hedge_value(ws, f, btc_lu, btc_keys, corr, n_ct=1, maker=True, k_cut=12, gap='hold'):
    """Per-contract value of an ETH strand hedged with the concurrent BTC 15-min binary.
    Delta-matched: scale the BTC binary's directional contribution by `corr` (the measured
    BTC/ETH co-move), capturing only the co-moving component (idiosyncratic ETH is NOT hedged)."""
    settle = f['settle']
    bk = nearest_key(ws, btc_keys)
    if bk is None or btc_lu.get(bk) is None:
        if gap == 'sellcheap':
            if p_yeq(f) < 0.30:
                return f.get('exit', settle)
        return settle
    btc_up, btc_yes_px, bspread, bk_slot, _, _ = btc_lu[bk]
    if bk_slot > k_cut:
        return settle
    if f['side'] == 'bid':           # ETH YES-strand (long up) -> buy BTC-NO (down)
        btc_entry = round(1 - btc_yes_px, 4)
        btc_win = (btc_up == 0)
    else:                             # ETH NO-strand -> buy BTC-YES
        btc_entry = btc_yes_px
        btc_win = (btc_up == 1)
    cost = btc_entry + (0.0 if maker else bspread / 2.0)
    payoff = 1.0 if btc_win else 0.0
    btc_pnl_per_ct = payoff - cost
    contrib = corr * n_ct * btc_pnl_per_ct
    return settle + contrib


# ============================================================
# REGRESSION: ETH-strand directional P&L on concurrent BTC move (the BASIS)
# ============================================================

def strand_directional_pnl(f):
    """The directional (settlement) P&L of holding the ETH strand naked, in $/contract.
    This is what a hedge must offset. settle already = (res-b) for YES / (a-res) for NO."""
    return f['settle']


def regress_basis(strands, btc_lu, btc_keys):
    """Regress the ETH-strand directional P&L on the concurrent BTC 15-min % move (signed to
    the strand's directional exposure). Returns dict with R^2, |corr|, std-reduction estimate,
    n_covered, coverage."""
    y = []   # ETH strand directional pnl (what we want to hedge)
    x = []   # BTC concurrent move signed so positive = adverse to the strand's hedge instrument
    n_cov = 0
    for ws, f in strands:
        bk = nearest_key(ws, btc_keys)
        if bk is None or btc_lu.get(bk) is None:
            continue
        n_cov += 1
        btc_up, _, _, _, s0, ss = btc_lu[bk]
        r_btc = (ss / s0 - 1.0) if (s0 and s0 > 0) else 0.0   # BTC fractional move
        # ETH strand directional exposure: YES-strand profits when ETH up; the hedge is BTC down.
        # The thing we regress: ETH strand pnl vs BTC move. Sign the BTC move to the strand's
        # directional sense: a YES-strand (long ETH-up) is helped by a positive co-move; the
        # hedge captures BTC's move in the SAME directional sense.
        sgn = 1.0 if f['side'] == 'bid' else -1.0
        x.append(sgn * r_btc)
        y.append(f['settle'])
    x = np.array(x, float); y = np.array(y, float)
    if len(x) < 8:
        return None
    # corr between strand pnl and the (signed) BTC move
    if x.std() < 1e-12 or y.std() < 1e-12:
        corr = 0.0
    else:
        corr = np.corrcoef(x, y)[0, 1]
    r2 = corr ** 2
    # OLS hedge: residual std after regressing y on x = std(y)*sqrt(1-r2)
    std_y = y.std(ddof=1)
    std_resid = std_y * np.sqrt(max(0.0, 1 - r2))
    std_red = (1 - std_resid / std_y) * 100 if std_y > 0 else 0.0
    # delta-matched (beta) hedge: beta = cov(y,x)/var(x); hedged pnl = y - beta*x
    if x.var() > 1e-18:
        beta = np.cov(y, x, ddof=1)[0, 1] / x.var(ddof=1)
    else:
        beta = 0.0
    hedged = y - beta * x
    return dict(n=len(x), n_cov=n_cov, corr=corr, abscorr=abs(corr), r2=r2,
                std_y=std_y * 100, std_resid=std_resid * 100, std_red=std_red,
                beta=beta, hedged_mean=hedged.mean() * 100, hedged_std=hedged.std(ddof=1) * 100,
                naked_mean=y.mean() * 100, naked_std=std_y * 100)


# ============================================================
# ETH-PERP at-scale (mirror of the BTC-perp lumpy model, using ETH spot)
# ============================================================

def eth_perp_value_lumpy(ws, f, box_ct):
    """ETH strand hedged with INTEGER ETH-perp contracts ($6 min). Uses the strand's own
    spot->sset (ETH) move. Per-contract: settle + sgn*(n_perp*$6)*r%/100 / box_ct."""
    s0, ss = f.get('spot'), f.get('sset')
    settle = f['settle']
    if not s0 or not ss or s0 <= 0:
        return settle
    r = (ss / s0 - 1.0) * 100.0
    sgn = -1.0 if f['side'] == 'bid' else 1.0
    target_usd = box_ct * DELTA_PER_CT_USD
    n_perp = int(np.floor(target_usd / PERP_MIN_USD + 0.5))
    if n_perp <= 0:
        return settle
    hedge_notional = n_perp * PERP_MIN_USD
    return settle + sgn * hedge_notional * r / 100.0 / box_ct


def main():
    print("=" * 80)
    print("ETH DISPOSAL LADDER STUDY (R3 complete / R4 sell / R5 hedge)")
    print("=" * 80)

    fe, we = L.load_parquet_windows('eth')
    fb, wb = L.load_parquet_windows('btc')
    n = len(we); cut = int(n * 0.6)
    we_is, we_oos = we[:cut], we[cut:]
    print(f"ETH windows={n} IS={len(we_is)} OOS={len(we_oos)}")

    # =====================================================
    # TASK 1: BASELINE strand cost
    # =====================================================
    print("\n" + "=" * 80)
    print("TASK 1: BASELINE ETH STRAND COST (P0 hold-to-settle)")
    print("=" * 80)
    p0_all, st_all = window_pnl_with_handler(fe, we, None)
    p0_is, st_is = window_pnl_with_handler(fe, we_is, None)
    p0_oos, st_oos = window_pnl_with_handler(fe, we_oos, None)
    m0a = L.full_metrics(p0_all, p0_all, p0_all)
    m0i = L.full_metrics(p0_is, p0_is, p0_is)
    m0o = L.full_metrics(p0_oos, p0_oos, p0_oos)
    print(f"P0 ALL: net={m0a['nc']:+.3f}c n={m0a['n']} strand={st_all.mean()*100:.1f}% win%={m0a['wr']:.1f} t={m0a['ts']:+.2f}")
    print(f"P0 IS : net={m0i['nc']:+.3f}c n={m0i['n']} strand={st_is.mean()*100:.1f}%")
    print(f"P0 OOS: net={m0o['nc']:+.3f}c n={m0o['n']} strand={st_oos.mean()*100:.1f}% t={m0o['ts']:+.2f}")

    strands_all = extract_strands(fe, we)
    strands_is = extract_strands(fe, we_is)
    strands_oos = extract_strands(fe, we_oos)
    print(f"\nStrands: ALL={len(strands_all)} IS={len(strands_is)} OOS={len(strands_oos)}")

    # strand cost in c/win = (P0 with strands held naked) minus (P0 if strands were free / paired at 0)
    # Decompose: total P0 = paired-box pnl + strand-leg pnl. Strand cost = sum(strand settle)/Nwin.
    strand_settle = np.array([f['settle'] for _, f in strands_all], float)
    strand_cost_per_win = strand_settle.sum() / n * 100
    # total loss attributable: compare to a counterfactual where strands cost 0
    paired_only_all = p0_all - np.array([0.0] * len(p0_all))  # placeholder
    print(f"\nStrand-leg naked settle: mean={strand_settle.mean()*100:+.2f}c std={strand_settle.std(ddof=1)*100:.2f}c")
    print(f"  neg%={(strand_settle<0).mean()*100:.1f}  p5={np.percentile(strand_settle,5)*100:+.1f}c  median={np.median(strand_settle)*100:+.2f}c")
    print(f"STRAND COST to ETH box = sum(strand settle)/Nwin = {strand_cost_per_win:+.3f} c/win")
    # what fraction of total negative pnl?
    tot_neg = p0_all[p0_all < 0].sum() * 100
    print(f"  Total P0 pnl/win = {m0a['nc']:+.3f}c; strand contributes {strand_cost_per_win:+.3f}c/win of that")

    # characterize strands: side, slot, price region
    print("\n--- STRAND CHARACTERIZATION (ALL) ---")
    yes_s = [(w, f) for w, f in strands_all if f['side'] == 'bid']
    no_s = [(w, f) for w, f in strands_all if f['side'] == 'ask']
    print(f"  YES-strands (bid): n={len(yes_s)} ({len(yes_s)/len(strands_all)*100:.0f}%) mean settle={np.mean([f['settle'] for _,f in yes_s])*100:+.2f}c")
    print(f"  NO-strands  (ask): n={len(no_s)} ({len(no_s)/len(strands_all)*100:.0f}%) mean settle={np.mean([f['settle'] for _,f in no_s])*100:+.2f}c")
    kk = np.array([f.get('k', 7) for _, f in strands_all])
    pp = np.array([p_yeq(f) for _, f in strands_all])
    sett = strand_settle
    def grp(mask, name):
        if mask.sum() == 0:
            print(f"    {name:<26} n=0"); return
        print(f"    {name:<26} n={int(mask.sum()):4} ({mask.mean()*100:4.0f}%) mean_settle={sett[mask].mean()*100:+7.2f}c neg%={(sett[mask]<0).mean()*100:4.0f}")
    print("  by SLOT:")
    grp(kk <= 4, "early k<=4")
    grp((kk >= 5) & (kk <= 9), "mid k5-9")
    grp(kk > 9, "late k>9")
    print("  by PRICE region (YES-equiv):")
    grp(pp < 0.20, "deep longshot <0.20")
    grp((pp >= 0.20) & (pp < 0.40), "cheap 0.20-0.40")
    grp((pp >= 0.40) & (pp <= 0.60), "midprice 0.40-0.60")
    grp((pp > 0.60) & (pp <= 0.80), "favorite 0.60-0.80")
    grp(pp > 0.80, "deep favorite >0.80")

    # =====================================================
    # TASK 2: R3 COMPLETE
    # =====================================================
    print("\n" + "=" * 80)
    print("TASK 2: R3 COMPLETE (chase/flatten the stranded ETH leg)")
    print("=" * 80)
    naked_mean = strand_settle.mean() * 100
    naked_std = strand_settle.std(ddof=1) * 100
    print(f"  [ref] naked strand hold: mean={naked_mean:+.2f}c std={naked_std:.2f}c")
    print(f"  {'give(c)':>8} {'strand_mean':>12} {'strand_std':>11} {'recover_vs_naked':>16}")
    for give in [0.0, 0.005, 0.01, 0.02, 0.03]:
        sm, ss, _ = strand_pool_stats(strands_all, lambda w, f, g=give: complete_value(w, f, give=g))
        print(f"  {give*100:>7.1f}c {sm:>+11.2f}c {ss:>10.2f}c {sm-naked_mean:>+15.2f}c")
    # window-level OOS for give=0 (flatten-at-touch, the deployable complete proxy)
    comp_oos, _ = window_pnl_with_handler(fe, we_oos, lambda w, f: complete_value(w, f, give=0.0))
    mc_o = L.full_metrics(comp_oos, p0_oos, p0_oos)
    comp_is, _ = window_pnl_with_handler(fe, we_is, lambda w, f: complete_value(w, f, give=0.0))
    mc_i = L.full_metrics(comp_is, p0_is, p0_is)
    print(f"\n  COMPLETE(give=0) window OOS: net={mc_o['nc']:+.3f}c (Δ{mc_o['nc']-m0o['nc']:+.3f}) sh={mc_o['sh']:+.3f} t={mc_o['ts']:+.2f} IR_vs_P0={mc_o['ir_p0']:+.3f}")
    print(f"  COMPLETE(give=0) window IS : net={mc_i['nc']:+.3f}c (Δ{mc_i['nc']-m0i['nc']:+.3f})")

    # =====================================================
    # TASK 3: R4 SELL-CHEAP  (ETH-tuned threshold sweep)
    # =====================================================
    print("\n" + "=" * 80)
    print("TASK 3: R4 SELL/MANAGE (ETH-tuned price-threshold sweep)")
    print("=" * 80)

    def sell_value(ws, f, cheap_below=None, tox_above=None, vpin_above=None):
        sell = True
        if cheap_below is not None:
            sell = p_yeq(f) < cheap_below
        if tox_above is not None:
            sell = tox_p(f) > tox_above
        if vpin_above is not None:
            v = f.get('vpin'); sell = (v is not None) and (v > vpin_above)
        return f.get('exit', f['settle']) if sell else f['settle']

    print("  PRICE-THRESHOLD SWEEP (sell if YES-equiv price < thr, else hold):")
    print(f"  {'thr':>6} {'strand_mean':>12} {'strand_std':>11} {'Δvs_naked':>10} {'OOSnet':>9} {'OOSt':>7}")
    best_thr = None; best_thr_mean = -1e9
    for thr in [0.20, 0.25, 0.30, 0.35, 0.40, 0.50, None]:
        sm, ss, _ = strand_pool_stats(strands_all, lambda w, f, t=thr: sell_value(w, f, cheap_below=t))
        so_oos, _ = window_pnl_with_handler(fe, we_oos, lambda w, f, t=thr: sell_value(w, f, cheap_below=t))
        mo = L.full_metrics(so_oos, p0_oos, p0_oos)
        lbl = f"{thr:.2f}" if thr is not None else "all"
        print(f"  {lbl:>6} {sm:>+11.2f}c {ss:>10.2f}c {sm-naked_mean:>+9.2f}c {mo['nc']:>+8.3f}c {mo['ts']:>+6.2f}")
        if sm > best_thr_mean:
            best_thr_mean = sm; best_thr = thr

    # price-bucket split: hold vs sell for cheap and expensive
    print("\n  HOLD vs SELL by price bucket (which legs benefit from selling?):")
    print(f"  {'bucket':>20} {'n':>5} {'hold_mean':>10} {'sell_mean':>10} {'Δsell-hold':>11}")
    for lo, hi, name in [(0.0, 0.20, "deep longshot<0.20"), (0.20, 0.40, "cheap 0.20-0.40"),
                         (0.40, 0.60, "mid 0.40-0.60"), (0.60, 0.80, "fav 0.60-0.80"),
                         (0.80, 1.01, "deep fav>0.80")]:
        sub = [(w, f) for w, f in strands_all if lo <= p_yeq(f) < hi]
        if not sub:
            print(f"  {name:>20} n=0"); continue
        hold = np.array([f['settle'] for _, f in sub]) * 100
        sell = np.array([f.get('exit', f['settle']) for _, f in sub]) * 100
        print(f"  {name:>20} {len(sub):>5} {hold.mean():>+9.2f}c {sell.mean():>+9.2f}c {sell.mean()-hold.mean():>+10.2f}c")

    # tox-conditioned + vpin-conditioned
    print("\n  TOX-CONDITIONED sell (sell only when fitted toxicity high):")
    for ta in [0.45, 0.55, 0.65]:
        sm, ss, _ = strand_pool_stats(strands_all, lambda w, f, t=ta: sell_value(w, f, tox_above=t))
        print(f"    tox>{ta:.2f}: strand mean={sm:+.2f}c std={ss:.2f}c (Δvs_naked {sm-naked_mean:+.2f}c)")
    for va in [0.40, 0.50]:
        sm, ss, _ = strand_pool_stats(strands_all, lambda w, f, t=va: sell_value(w, f, vpin_above=t))
        print(f"    vpin>{va:.2f}: strand mean={sm:+.2f}c std={ss:.2f}c (Δvs_naked {sm-naked_mean:+.2f}c)")

    # best sell config window-level IS/OOS
    print(f"\n  => best price-threshold (by strand mean): {best_thr}")

    # =====================================================
    # TASK 4: R5 HEDGE (headline)
    # =====================================================
    print("\n" + "=" * 80)
    print("TASK 4: R5 HEDGE (headline) -- BTC cross-asset hedge of ETH strand")
    print("=" * 80)

    btc_lu = build_btc_lookup(fb, wb)
    btc_keys = sorted(btc_lu.keys())
    cov = sum(1 for w, _ in strands_all if nearest_key(w, btc_keys) is not None)
    print(f"\n  (c) COVERAGE: BTC windows usable={len(btc_keys)}; ETH-strand coverage "
          f"{cov}/{len(strands_all)} = {cov/len(strands_all)*100:.0f}% (concurrent BTC window within 450s)")

    # (a) the BASIS regression -- the MIRROR of the 18.6% symmetric finding
    print("\n  (a) BASIS REGRESSION: ETH-strand directional P&L on concurrent BTC 15-min move")
    reg = regress_basis(strands_all, btc_lu, btc_keys)
    reg_oos = regress_basis(strands_oos, btc_lu, btc_keys)
    if reg:
        print(f"    ALL  n_cov={reg['n']:>4}: |corr|={reg['abscorr']:.3f}  R^2={reg['r2']*100:.1f}%  "
              f"std_red(OLS)={reg['std_red']:.1f}%  beta={reg['beta']:+.4f}")
        print(f"      naked strand mean={reg['naked_mean']:+.2f}c std={reg['naked_std']:.2f}c -> "
              f"delta-matched hedged mean={reg['hedged_mean']:+.2f}c std={reg['hedged_std']:.2f}c")
    if reg_oos:
        print(f"    OOS  n_cov={reg_oos['n']:>4}: |corr|={reg_oos['abscorr']:.3f}  R^2={reg_oos['r2']*100:.1f}%  "
              f"std_red(OLS)={reg_oos['std_red']:.1f}%")
    print(f"    [established symmetric: ETH hedges BTC at R^2=18.6% / |corr|~0.43]")

    measured_corr = reg['abscorr'] if reg else 0.43

    # delta-matched binary-hedge value sweep (using measured corr as the delta scaler)
    print("\n  BTC-binary hedge value (delta-matched by measured |corr|):")
    print(f"  {'n_ct':>5} {'mode':>5} {'k_cut':>6} {'gap':>10} {'strand_mean':>12} {'strand_std':>11} {'std_red%':>9}")
    hedge_best = None
    for n_ct in [1, 2]:
        for maker in [True, False]:
            for k_cut in [10, 12]:
                for gap in ['hold', 'sellcheap']:
                    vals = np.array([btc_hedge_value(w, f, btc_lu, btc_keys, measured_corr,
                                                      n_ct=n_ct, maker=maker, k_cut=k_cut, gap=gap)
                                     for w, f in strands_all], float)
                    sm = vals.mean() * 100; ss = vals.std(ddof=1) * 100
                    std_red = (1 - ss / naked_std) * 100 if naked_std > 0 else 0.0
                    if (maker and k_cut == 12) or (gap == 'sellcheap' and maker):
                        print(f"  {n_ct:>5} {('mkr' if maker else 'tkr'):>5} {k_cut:>6} {gap:>10} "
                              f"{sm:>+11.2f}c {ss:>10.2f}c {std_red:>+8.1f}%")
                    cand = (std_red > 0) and (sm >= naked_mean - 0.5)
                    tag = (n_ct, 'mkr' if maker else 'tkr', k_cut, gap, sm, ss, std_red)
                    if cand and (hedge_best is None or std_red > hedge_best[6]):
                        hedge_best = tag
    if hedge_best is None:
        vals = np.array([btc_hedge_value(w, f, btc_lu, btc_keys, measured_corr, n_ct=1, maker=True, k_cut=12, gap='hold')
                         for w, f in strands_all], float)
        sm = vals.mean() * 100; ss = vals.std(ddof=1) * 100
        hedge_best = (1, 'mkr', 12, 'hold', sm, ss, (1 - ss / naked_std) * 100)
        print("    NOTE: no BTC-binary config REDUCED strand-pool variance.")
    print(f"  => BTC-hedge best: n_ct={hedge_best[0]} {hedge_best[1]} k_cut={hedge_best[2]} gap={hedge_best[3]} "
          f"mean={hedge_best[4]:+.2f}c std={hedge_best[5]:.2f}c std_red={hedge_best[6]:+.1f}%")

    # (b) ETH-perp at scale (lumpy)
    print("\n  (b) ETH-PERP at scale (integer-contract lumpy, $6 min):")
    print(f"  {'box_ct':>7} {'box$':>7} {'n_perp':>7} {'over/under':>11} {'strand_mean':>12} {'strand_std':>11} {'std_red%':>9}")
    eth_perp_thresh = None
    for box_ct in [1, 2, 3, 4, 6, 8, 10, 12, 15, 20, 30, 50]:
        target = box_ct * DELTA_PER_CT_USD
        n_perp = int(np.floor(target / PERP_MIN_USD + 0.5))
        over = (n_perp * PERP_MIN_USD / target) if (target > 0 and n_perp > 0) else 0.0
        sm, ss, _ = strand_pool_stats(strands_all, lambda w, f, bc=box_ct: eth_perp_value_lumpy(w, f, bc))
        std_red = (1 - ss / naked_std) * 100 if naked_std > 0 else 0.0
        ratio_s = f"{over:.2f}x" if n_perp > 0 else "no hedge"
        print(f"  {box_ct:>7} {box_ct*BASE_BOX_USD:>6.0f}$ {n_perp:>7} {ratio_s:>11} {sm:>+11.2f}c {ss:>10.2f}c {std_red:>+8.1f}%")
        if eth_perp_thresh is None and n_perp >= 1 and 0.6 <= over <= 1.6 and ss <= naked_std:
            eth_perp_thresh = box_ct
    print(f"  => ETH-perp scale threshold: box_ct>={eth_perp_thresh} (~${(eth_perp_thresh or 0)*BASE_BOX_USD:.0f}/window)"
          if eth_perp_thresh else "  => no box_ct gives a proper variance-reducing ETH-perp hedge")

    # hedge window-level OOS (BTC binary best)
    hb = hedge_best
    btc_hedge_oos, _ = window_pnl_with_handler(fe, we_oos, lambda w, f: btc_hedge_value(
        w, f, btc_lu, btc_keys, measured_corr, n_ct=hb[0], maker=(hb[1] == 'mkr'), k_cut=hb[2], gap=hb[3]))
    mh_o = L.full_metrics(btc_hedge_oos, p0_oos, p0_oos)
    print(f"\n  BTC-hedge window OOS: net={mh_o['nc']:+.3f}c (Δ{mh_o['nc']-m0o['nc']:+.3f}) sh={mh_o['sh']:+.3f} cv95={mh_o['cv95']:.2f}c t={mh_o['ts']:+.2f}")

    # =====================================================
    # TASK 5: STACK best disposal rungs
    # =====================================================
    print("\n" + "=" * 80)
    print("TASK 5: STACK best disposal rungs (ETH)")
    print("=" * 80)

    # determine per-rung winner on the strand pool:
    # COMPLETE(flatten) gives strand mean ~exit; SELL-cheap@best_thr; HEDGE BTC.
    # Build the best stacked disposal handler: for each strand, choose the deployable rung.
    # ETH-tuned stack: SELL-cheap below ETH cut (best_thr), else COMPLETE/flatten the rest,
    # optionally overlay BTC hedge on the held legs (coverage permitting).
    def stack_value(ws, f, thr, use_hedge=False):
        py = p_yeq(f)
        if thr is not None and py < thr:
            return f.get('exit', f['settle'])      # SELL cheap
        if use_hedge:
            return btc_hedge_value(ws, f, btc_lu, btc_keys, measured_corr,
                                   n_ct=hb[0], maker=(hb[1] == 'mkr'), k_cut=hb[2], gap='hold')
        return f.get('exit', f['settle'])          # else flatten (COMPLETE)

    print("\n  Stacked-disposal variants (window-level, IS/OOS):")
    print(f"  {'variant':>34} {'ISnet':>9} {'OOSnet':>9} {'ΔOOS':>8} {'OOSt':>7} {'IR_P0':>7} {'OOSsh':>7}")
    variants = [
        ("naked P0 (hold to settle)", None, False, 'naked'),
        ("flatten-all (COMPLETE)", None, False, 'flatten'),
        (f"sell<{best_thr} else flatten", best_thr, False, 'stack'),
        (f"sell<{best_thr} else BTC-hedge", best_thr, True, 'stack'),
    ]
    stack_results = {}
    for name, thr, uh, kind in variants:
        if kind == 'naked':
            xi, xo = p0_is, p0_oos
        elif kind == 'flatten':
            xi, _ = window_pnl_with_handler(fe, we_is, lambda w, f: f.get('exit', f['settle']))
            xo, _ = window_pnl_with_handler(fe, we_oos, lambda w, f: f.get('exit', f['settle']))
        else:
            xi, _ = window_pnl_with_handler(fe, we_is, lambda w, f, t=thr, u=uh: stack_value(w, f, t, u))
            xo, _ = window_pnl_with_handler(fe, we_oos, lambda w, f, t=thr, u=uh: stack_value(w, f, t, u))
        mi = L.full_metrics(xi, p0_is, p0_is); mo = L.full_metrics(xo, p0_oos, p0_oos)
        print(f"  {name:>34} {mi['nc']:>+8.3f}c {mo['nc']:>+8.3f}c {mo['nc']-m0o['nc']:>+7.3f}c {mo['ts']:>+6.2f} {mo['ir_p0']:>+6.3f} {mo['sh']:>+6.3f}")
        stack_results[name] = (mi, mo, xi, xo)

    # net effect on ETH box: does disposal alone move ETH toward profitable?
    print("\n  NET EFFECT ON ETH BOX (best disposal stack vs naked P0):")
    best_name = f"sell<{best_thr} else flatten"
    mi_b, mo_b, xi_b, xo_b = stack_results[best_name]
    # paired t-test OOS: stack - naked
    d_oos = xo_b - p0_oos
    from scipy import stats as _st
    t_paired = d_oos.mean() / (d_oos.std(ddof=1) / np.sqrt(len(d_oos))) if d_oos.std() > 0 else float('nan')
    print(f"  best stack = {best_name}")
    print(f"  OOS net: naked {m0o['nc']:+.3f}c -> stack {mo_b['nc']:+.3f}c  (Δ={mo_b['nc']-m0o['nc']:+.3f}c/win, paired t={t_paired:+.2f})")
    print(f"  IS  net: naked {m0i['nc']:+.3f}c -> stack {mi_b['nc']:+.3f}c")
    print(f"  Strand-loss reduction OOS: {mo_b['nc']-m0o['nc']:+.3f}c/win recovered")

    # save a small results dict for the writer
    results = dict(
        n=n, n_is=len(we_is), n_oos=len(we_oos),
        m0a=m0a, m0i=m0i, m0o=m0o,
        st_all=st_all.mean()*100, st_is=st_is.mean()*100, st_oos=st_oos.mean()*100,
        n_strands=len(strands_all), n_strands_oos=len(strands_oos),
        strand_mean=naked_mean, strand_std=naked_std,
        strand_neg=(strand_settle<0).mean()*100, strand_p5=np.percentile(strand_settle,5)*100,
        strand_med=np.median(strand_settle)*100, strand_cost=strand_cost_per_win,
        n_yes=len(yes_s), n_no=len(no_s),
        yes_mean=np.mean([f['settle'] for _,f in yes_s])*100,
        no_mean=np.mean([f['settle'] for _,f in no_s])*100,
        complete_oos=mc_o, complete_is=mc_i,
        best_thr=best_thr, best_thr_mean=best_thr_mean,
        reg=reg, reg_oos=reg_oos, measured_corr=measured_corr,
        cov=cov, hedge_best=hedge_best, mh_o=mh_o, eth_perp_thresh=eth_perp_thresh,
        stack_best_name=best_name, stack_mi=mi_b, stack_mo=mo_b, t_paired=t_paired,
    )
    import pickle
    with open('/tmp/eth_disposal/_eth_disposal_results.pkl', 'wb') as fh:
        pickle.dump(results, fh)
    print("\nSaved results pickle. Run eth_disposal_report.py to write ETH_DISPOSAL.md")
    return results


if __name__ == '__main__':
    main()
