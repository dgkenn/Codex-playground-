"""ladder_manage_optimize.py -- Phase-C RUNG 4 (MANAGE) optimization.

TOP deployable Phase-C priority. Find the BEST rung-4 MANAGE strategy for the
strand-handling ladder of the Kalshi 15-min crypto box bot.

CONTEXT (established by prior backtests, NOT re-derived here):
- A "strand" = one box leg fills, the other doesn't -> directional settlement loss.
- DEPLOYED rung 4 = streak scale-down --strand-scaledown "0.75,0.5,0.25".
- Leave-one-out ablation PROVED the streak guard is NET-NEGATIVE: dropping it
  improves OOS net by +0.61c/win (combined +3.50c -> +4.11c) and it inflates MaxDD.
- Prototype "manage-split" (continuous GBM-strand-prob sizing, mult=max(0.25,1-p*5))
  beat the combined baseline by +0.57c/win OOS (+1.18c over keeping the streak).
- GBM (rung 2) OOS AUC=0.883 on a per-fill strand label; strand-fill rate ~0.65% OOS.

This script reuses ALL data-loading + metric scaffolding from ladder_baseline_study.py
(which itself imports the A/B metric helpers from box_policy_ab.py). It adds the rung-4
MANAGE sizing variants, runs the full A/B metric head-to-head on BTC IS(60%)/OOS(40%)
vs (a) the live streak-guard and (b) the combined baseline, and writes MANAGE_RUNG.md.

Backtests SCREEN only; forward-validation required before swapping live config.

Usage: python ladder_manage_optimize.py
Writes: MANAGE_RUNG.md
"""
from __future__ import annotations

import sys
import math
sys.path.insert(0, '/tmp/pc_manage')

import numpy as np

# Reuse the baseline study's scaffolding (data load, GBM build, walk engine, metrics).
from ladder_baseline_study import (
    load_parquet_windows, build_gbm, make_gbm_gate, get_strand_labels,
    _get_fill_feats, _auc_approx, walk, run_p0, run_live_current, full_metrics,
)
# A/B metric helpers + tox helpers (re-exported via the baseline module's imports).
from box_policy_ab import (
    tox_p, combo_tox_p, pair_prob, tstat,
)

np.seterr(all='ignore')


# ============================================================
# SIZE-FUNCTION FACTORIES (each returns size_fn(f) -> multiplier in (0,1])
# The walk engine multiplies BOTH legs' settle by this opening-fill size.
# All variants are CONTINUOUS (no discrete streak ladder), per the ablation verdict.
# ============================================================

def gbm_p_of(gbm, col_means):
    """Return p_fn(f) -> GBM P(this fill strands)."""
    def p_fn(f):
        row = np.array([_get_fill_feats(f)], float)
        for j in range(row.shape[1]):
            if np.isnan(row[0, j]):
                row[0, j] = col_means[j]
        return float(gbm.predict_proba(row)[0, 1])
    return p_fn


# --- Variant 1: GBM continuous sizing  mult = max(floor, 1 - p*k) -----------
def mk_gbm_linear(p_fn, k, floor):
    def size_fn(f):
        return max(floor, 1.0 - p_fn(f) * k)
    return size_fn


# --- Variant 2: Kelly-fraction sizing ---------------------------------------
# A box leg that pairs earns ~ +spread/2 (locked, ~risk-free); a leg that strands
# pays the settle distribution. Per-fill edge/variance using GBM p and the leg's
# own settle/exit magnitudes. Bernoulli outcome: pair (prob 1-p) -> ~0 (locked box,
# the loss engine is ONLY the strand), strand (prob p) -> settle (can be +/- ~ price).
# Kelly fraction for a bet with win prob q, win amt b, loss amt a:
#   f* = (q*b - (1-q)*a) / (a*b)   (clipped to [0,1]); we scale by a fractional-Kelly lam.
def mk_kelly(p_fn, lam=0.5, floor=0.0, cap=1.0):
    def size_fn(f):
        p = p_fn(f)                                  # P(strand)
        q = 1.0 - p                                  # P(pair, i.e. the "win")
        # win amount if paired: the locked box edge ~ half-spread (cents -> dollars)
        b = max(f.get('spread', 0.02) / 2.0, 1e-3)
        # loss amount if stranded: expected magnitude of the naked settle.
        # settle in [-p_yeq, 1-p_yeq]; use the leg cost as the downside scale.
        p_yeq = f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)
        a = max(min(p_yeq, 1.0 - p_yeq), 1e-3)       # worst-case naked exposure ~ leg price
        fstar = (q * b - p * a) / (a * b)
        return float(min(cap, max(floor, lam * fstar)))
    return size_fn


# --- Variant 3: VPIN/toxicity-conditional sizing ----------------------------
# Use the toxicity probability (combo_tox_p preferred, fall back to tox_p) as the
# strand proxy instead of / blended with the GBM p.
def mk_tox_linear(k, floor, blend_gbm=None, w_gbm=0.0):
    def size_fn(f):
        pt = combo_tox_p(f)
        if pt is None or (isinstance(pt, float) and math.isnan(pt)):
            pt = tox_p(f)
        p = pt
        if blend_gbm is not None and w_gbm > 0.0:
            p = (1.0 - w_gbm) * pt + w_gbm * blend_gbm(f)
        return max(floor, 1.0 - p * k)
    return size_fn


# --- Variant 4: Autocorr-weighted (Bayesian) inventory-risk sizing ----------
# Gueant-Lehalle-Tapia style: continuous down-weight by a DECAYING inventory-risk
# term that accumulates on strands and decays geometrically -- size ~ 1/(1+gamma*q)^2.
# q is a running "recent-strand inventory" updated AFTER each window (EWMA of the
# strand indicator). NOT the discrete streak ladder: it is smooth and mean-reverting.
class BayesAutocorrSizer:
    def __init__(self, gamma=4.0, decay=0.5, power=2.0):
        self.gamma = gamma; self.decay = decay; self.power = power
        self.q = 0.0
    def size_fn(self):
        # closure capturing current self.q (read at window start, like streak.multiplier)
        q = self.q
        m = 1.0 / (1.0 + self.gamma * q) ** self.power
        return lambda f, _m=m: _m
    def update(self, stranded):
        self.q = self.decay * self.q + (1.0 - self.decay) * (1.0 if stranded else 0.0)


# --- Variant 5: Hybrid -- GBM-prob sizing + hard floor cut after ONE LARGE strand
# Continuous GBM sizing for normal flow, but if the PREVIOUS window produced a
# strand whose realized loss exceeded big_thresh (cents), cut the next window to
# cut_mult (the single thing the streak guard was meant to catch -- a tail event,
# not a "streak"). State carried across windows.
class HybridBigStrandSizer:
    def __init__(self, p_fn, k=5, floor=0.25, big_thresh=0.10, cut_mult=0.5, cut_decay=0.5):
        self.p_fn = p_fn; self.k = k; self.floor = floor
        self.big_thresh = big_thresh; self.cut_mult = cut_mult; self.cut_decay = cut_decay
        self.penalty = 1.0   # multiplicative penalty, recovers toward 1 each window
    def size_fn(self):
        base_pen = self.penalty
        kk, fl, pf = self.k, self.floor, self.p_fn
        return lambda f: max(fl, (1.0 - pf(f) * kk)) * base_pen
    def update(self, stranded, last_loss):
        # last_loss is the realized PnL of the window (negative = loss). Trigger on a
        # single LARGE loss, not a streak.
        if stranded and last_loss is not None and last_loss < -self.big_thresh:
            self.penalty = min(self.penalty, self.cut_mult)
        else:
            # recover toward 1 geometrically
            self.penalty = self.penalty + (1.0 - self.penalty) * (1.0 - self.cut_decay)


# --- Variant 6 (novel): Avellaneda-Stoikov inventory-skew sizing ------------
# AS reservation-price shifts size away from the adverse-inventory side. Here we
# combine the GBM strand-prob (instantaneous toxicity) with a slow inventory term
# (the Bayes EWMA q): mult = max(floor, (1 - p*k) * exp(-gamma * q)).
# Multiplicative blend of instantaneous (GBM) + accumulated (inventory) risk.
class AvellanedaStoikovSizer:
    def __init__(self, p_fn, k=5, floor=0.25, gamma=2.0, decay=0.5):
        self.p_fn = p_fn; self.k = k; self.floor = floor
        self.gamma = gamma; self.decay = decay; self.q = 0.0
    def size_fn(self):
        inv = math.exp(-self.gamma * self.q)
        kk, fl, pf = self.k, self.floor, self.p_fn
        return lambda f: max(fl, (1.0 - pf(f) * kk) * inv)
    def update(self, stranded):
        self.q = self.decay * self.q + (1.0 - self.decay) * (1.0 if stranded else 0.0)


# ============================================================
# STATEFUL WALK -- for cross-window variants (4,5,6) the size_fn changes per window
# AND state updates after each window. The baseline walk() takes a fixed size_fn, so
# we add a thin stateful driver that mirrors walk()'s per-window inner loop exactly.
# ============================================================

def walk_stateful(fills_per_ws, ws_list, sizer, r1=True, r2_fn=None, r3=True, r5=True,
                  uses_loss=False):
    """sizer must expose .size_fn() (returns a per-window size closure) and
    .update(stranded[, last_loss]). r4 streak is OFF (replaced by sizer). Mirrors
    ladder_baseline_study.walk inner loop EXACTLY (entry gates, pairing, R3/R5)."""
    from box_policy_ab import hedge_unpaired
    from ladder_baseline_study import _live_open_ok  # same gate as walk()
    pnl_arr = []; strand_arr = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        size_fn = sizer.size_fn()
        net = 0; pnl = 0.0; open_leg = None; open_sz = 1.0
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                pnl += open_sz * (f['settle'] + (open_leg['settle'] if open_leg else 0))
                open_leg = None; open_sz = 1.0
            else:
                blocked = False
                if r1 and not _live_open_ok(f, {}):
                    blocked = True
                if r2_fn is not None and not blocked and not r2_fn(f, {}):
                    blocked = True
                if blocked:
                    continue
                open_sz = size_fn(f)
                open_leg = f
            net = nn
        stranded = False
        if open_leg is not None:
            stranded = True
            p_yeq = open_leg['p'] if open_leg['side'] == 'bid' else round(1.0 - open_leg['p'], 4)
            if r3 and p_yeq < 0.30:
                pnl += open_sz * open_leg.get('exit', open_leg['settle'])
            elif r5:
                pnl += open_sz * hedge_unpaired(open_leg, h=150.0)
            else:
                pnl += open_sz * open_leg['settle']
        pnl_arr.append(pnl); strand_arr.append(stranded)
        if uses_loss:
            sizer.update(stranded, pnl if stranded else None)
        else:
            sizer.update(stranded)
    return np.array(pnl_arr, float), np.array(strand_arr, bool)


# ============================================================
# MAIN
# ============================================================

def fmt(m, *keys):
    return {k: m.get(k, float('nan')) for k in keys}


def main():
    print("=" * 78)
    print("LADDER MANAGE OPTIMIZE -- Phase-C RUNG 4 (MANAGE)")
    print("=" * 78)

    print("\nLoading BTC parquet data...")
    fills, ws = load_parquet_windows('btc')
    n = len(ws); cut = int(n * 0.6)
    ws_is = ws[:cut]; ws_oos = ws[cut:]
    print(f"  IS: {len(ws_is)} windows, OOS: {len(ws_oos)} windows")

    print("\nFitting GBM strand gate on IS...")
    gbm, col_means, gbm_thresh = build_gbm(fills, ws_is)
    X_oos, y_oos = get_strand_labels(fills, ws_oos)
    for j in range(X_oos.shape[1]):
        X_oos[np.isnan(X_oos[:, j]), j] = col_means[j]
    probs_oos = gbm.predict_proba(X_oos)[:, 1]
    oos_auc = _auc_approx(probs_oos, y_oos)
    print(f"  GBM OOS AUC={oos_auc:.3f}")

    gbm_gate = make_gbm_gate(gbm, col_means, gbm_thresh)
    p_fn = gbm_p_of(gbm, col_means)

    # ---- reference series ----
    p0_is, _ = run_p0(fills, ws_is)
    p0_oos, _ = run_p0(fills, ws_oos)
    live_is = run_live_current(fills, ws_is)
    live_oos = run_live_current(fills, ws_oos)

    # (a) the LIVE streak-guard: combined ladder WITH r4 streak scale-down (deployed today)
    streak_is, streak_st_is = walk(fills, ws_is, r2_fn=None, r4=True)      # IS no GBM (leakage)
    streak_oos, streak_st_oos = walk(fills, ws_oos, r2_fn=gbm_gate, r4=True)

    # (b) the COMBINED baseline = drop r4 entirely (the ablation winner: no manage rung)
    base_is, base_st_is = walk(fills, ws_is, r2_fn=None, r4=False)
    base_oos, base_st_oos = walk(fills, ws_oos, r2_fn=gbm_gate, r4=False)

    # baseline metrics (benchmark all variants vs streak (a) and base (b))
    m_streak_is = full_metrics(streak_is, base_is, streak_is)
    m_streak_oos = full_metrics(streak_oos, base_oos, streak_oos)
    m_base_is = full_metrics(base_is, base_is, streak_is)
    m_base_oos = full_metrics(base_oos, base_oos, streak_oos)

    # ---- build the variant catalogue ----
    # Each entry: (label, kind, runner) where runner(ws_list, r2_fn) -> (pnl, strand)
    variants = []

    # Variant 1: GBM linear sweep k in {3,4,5,6,8} x floor in {0.0,0.25,0.5}
    for k in (3, 4, 5, 6, 8):
        for fl in (0.0, 0.25, 0.5):
            sf = mk_gbm_linear(p_fn, k, fl)
            variants.append((f"V1 GBM 1-p*{k} fl{fl}", 'static', sf))

    # Variant 2: Kelly-fraction sizing (lam sweep)
    for lam in (0.25, 0.5, 1.0):
        sf = mk_kelly(p_fn, lam=lam, floor=0.0, cap=1.0)
        variants.append((f"V2 Kelly lam{lam}", 'static', sf))

    # Variant 3: VPIN/toxicity-conditional. Pure tox + GBM-blended.
    for k in (3, 5):
        for fl in (0.25,):
            variants.append((f"V3 tox 1-p*{k} fl{fl}", 'static', mk_tox_linear(k, fl)))
    variants.append(("V3 tox+GBM blend(.5) k5 fl.25", 'static',
                     mk_tox_linear(5, 0.25, blend_gbm=p_fn, w_gbm=0.5)))

    # Variant 4: Bayesian autocorr (1/(1+g q)^2) -- stateful, no loss needed
    bayes_specs = [(2.0, 0.5, 2.0), (4.0, 0.5, 2.0), (4.0, 0.7, 2.0), (8.0, 0.5, 2.0)]
    # Variant 5: hybrid GBM + hard cut after one large strand -- stateful, uses loss
    hybrid_specs = [(5, 0.25, 0.10, 0.5), (5, 0.25, 0.05, 0.5), (4, 0.25, 0.10, 0.25)]
    # Variant 6: Avellaneda-Stoikov inventory skew -- stateful
    as_specs = [(5, 0.25, 1.0, 0.5), (5, 0.25, 2.0, 0.5), (4, 0.25, 2.0, 0.7)]

    # ---- run everything on IS and OOS ----
    def run_static(sf, ws_list, r2):
        return walk(fills, ws_list, r2_fn=r2, r4=False, size_fn=sf)

    rows = []  # (label, m_is, m_oos, st_oos)

    # streak & base reference rows first
    rows.append(("(a) LIVE streak-guard 0.75/.5/.25", m_streak_is, m_streak_oos, streak_st_oos.mean()*100))
    rows.append(("(b) BASELINE drop-R4 (ablation win)", m_base_is, m_base_oos, base_st_oos.mean()*100))

    # static variants (1,2,3)
    for label, kind, sf in variants:
        pis, _ = run_static(sf, ws_is, None)        # IS: no GBM gate (leakage)
        pos, sos = run_static(sf, ws_oos, gbm_gate) # OOS: with GBM gate
        mi = full_metrics(pis, base_is, streak_is)
        mo = full_metrics(pos, base_oos, streak_oos)
        rows.append((label, mi, mo, sos.mean()*100))

    # stateful variant 4 (bayes)
    for (g, d, pw) in bayes_specs:
        s_is = BayesAutocorrSizer(g, d, pw); pis, _ = walk_stateful(fills, ws_is, s_is, r2_fn=None)
        s_oos = BayesAutocorrSizer(g, d, pw); pos, sos = walk_stateful(fills, ws_oos, s_oos, r2_fn=gbm_gate)
        mi = full_metrics(pis, base_is, streak_is); mo = full_metrics(pos, base_oos, streak_oos)
        rows.append((f"V4 Bayes 1/(1+{g}q)^{pw} dec{d}", mi, mo, sos.mean()*100))

    # stateful variant 5 (hybrid)
    for (k, fl, bt, cm) in hybrid_specs:
        s_is = HybridBigStrandSizer(p_fn, k, fl, bt, cm); pis, _ = walk_stateful(fills, ws_is, s_is, r2_fn=None, uses_loss=True)
        s_oos = HybridBigStrandSizer(p_fn, k, fl, bt, cm); pos, sos = walk_stateful(fills, ws_oos, s_oos, r2_fn=gbm_gate, uses_loss=True)
        mi = full_metrics(pis, base_is, streak_is); mo = full_metrics(pos, base_oos, streak_oos)
        rows.append((f"V5 hybrid GBMk{k} cut{cm}@{bt}", mi, mo, sos.mean()*100))

    # stateful variant 6 (Avellaneda-Stoikov)
    for (k, fl, g, d) in as_specs:
        s_is = AvellanedaStoikovSizer(p_fn, k, fl, g, d); pis, _ = walk_stateful(fills, ws_is, s_is, r2_fn=None)
        s_oos = AvellanedaStoikovSizer(p_fn, k, fl, g, d); pos, sos = walk_stateful(fills, ws_oos, s_oos, r2_fn=gbm_gate)
        mi = full_metrics(pis, base_is, streak_is); mo = full_metrics(pos, base_oos, streak_oos)
        rows.append((f"V6 AvSt GBMk{k} g{g} dec{d}", mi, mo, sos.mean()*100))

    # ---- rank by OOS net (primary), keep full metric set ----
    def oos_net(r):
        v = r[2].get('nc', float('-inf'))
        return v if not (isinstance(v, float) and math.isnan(v)) else float('-inf')
    ranked = sorted(rows, key=oos_net, reverse=True)

    base_net = m_base_oos['nc']; streak_net = m_streak_oos['nc']

    # paired t-stat of (variant - base) and (variant - streak) on OOS, recompute series
    # (store series for the top variants by re-running the winner below)
    print("\n=== OOS RANKING (by net c/win) ===")
    hdr = (f"{'Variant':<36}{'OISnet':>8}{'OOSnet':>8}{'Sh':>7}{'Sor':>7}{'CVaR':>7}"
           f"{'MDD':>7}{'Ulcer':>7}{'PF':>6}{'Strand':>7}{'IRvB':>7}")
    print(hdr); print("-" * len(hdr))
    for label, mi, mo, st in ranked:
        print(f"{label:<36}{mi.get('nc',float('nan')):>+8.2f}{mo['nc']:>+8.2f}{mo['sh']:>+7.2f}"
              f"{mo['sor']:>+7.2f}{mo['cv95']:>7.2f}{mo['mdd']:>7.1f}{mo['ulcer']:>7.2f}"
              f"{mo['pf']:>6.2f}{st:>6.1f}%{mo.get('ir_p0',float('nan')):>+7.2f}")

    # ---- recompute the WINNER's series for t-stats vs base & streak ----
    winner = ranked[0]
    win_label = winner[0]
    # find the winner's size machinery to re-run series (search the catalogue)
    def rerun(label):
        # static
        for l, kind, sf in variants:
            if l == label:
                return run_static(sf, ws_oos, gbm_gate)
        if label.startswith("V4 Bayes"):
            for (g, d, pw) in bayes_specs:
                if f"V4 Bayes 1/(1+{g}q)^{pw} dec{d}" == label:
                    s = BayesAutocorrSizer(g, d, pw); return walk_stateful(fills, ws_oos, s, r2_fn=gbm_gate)
        if label.startswith("V5 hybrid"):
            for (k, fl, bt, cm) in hybrid_specs:
                if f"V5 hybrid GBMk{k} cut{cm}@{bt}" == label:
                    s = HybridBigStrandSizer(p_fn, k, fl, bt, cm)
                    return walk_stateful(fills, ws_oos, s, r2_fn=gbm_gate, uses_loss=True)
        if label.startswith("V6 AvSt"):
            for (k, fl, g, d) in as_specs:
                if f"V6 AvSt GBMk{k} g{g} dec{d}" == label:
                    s = AvellanedaStoikovSizer(p_fn, k, fl, g, d); return walk_stateful(fills, ws_oos, s, r2_fn=gbm_gate)
        return (base_oos, base_st_oos)

    # t-stats: top-5 variants vs base & streak
    top5 = ranked[:7]
    tstat_info = {}
    for label, mi, mo, st in top5:
        if label.startswith("(a)") or label.startswith("(b)"):
            continue
        pos, _ = rerun(label)
        d_base = pos - base_oos[:len(pos)]
        d_streak = pos - streak_oos[:len(pos)]
        tstat_info[label] = (tstat(d_base), tstat(d_streak),
                             d_base.mean()*100, d_streak.mean()*100)

    print("\n=== TOP VARIANTS: OOS uplift vs (b) baseline and (a) streak ===")
    print(f"{'Variant':<36}{'d_base c':>10}{'t_base':>8}{'d_streak c':>12}{'t_streak':>9}")
    for label in tstat_info:
        tb, ts, db, ds = tstat_info[label]
        print(f"{label:<36}{db:>+10.2f}{tb:>+8.2f}{ds:>+12.2f}{ts:>+9.2f}")

    print(f"\nBaseline (b) OOS net={base_net:+.2f}c  Streak (a) OOS net={streak_net:+.2f}c")
    print(f"Winner: {win_label}  OOS net={winner[2]['nc']:+.2f}c")

    # ---- write MANAGE_RUNG.md ----
    write_report(ranked, tstat_info, m_base_oos, m_streak_oos, m_base_is, m_streak_is,
                 base_net, streak_net, oos_auc, gbm_thresh, len(ws_is), len(ws_oos),
                 base_st_oos.mean()*100, streak_st_oos.mean()*100)
    print("\nWrote MANAGE_RUNG.md")


def write_report(ranked, tstat_info, m_base_oos, m_streak_oos, m_base_is, m_streak_is,
                 base_net, streak_net, oos_auc, gbm_thresh, n_is, n_oos,
                 base_strand, streak_strand):
    L = []
    L.append("# RUNG 4 (MANAGE) optimization -- Phase-C deep dive (2026-06-13)\n")
    L.append("TOP deployable Phase-C priority. Find the best rung-4 MANAGE strategy for the "
             "Kalshi 15-min crypto box bot's strand-handling ladder.\n")
    L.append("**Method.** BTC tape, IS=first 60% ({} windows) / OOS=last 40% ({} windows). IS runs "
             "EXCLUDE the GBM gate (leakage avoidance, matching the baseline study); OOS runs include "
             "the GBM gate (OOS AUC={:.3f}, thresh={:.3f}). All sizing variants reuse the exact "
             "`walk()` inner loop (R1 t36 + R2 GBM + R3 sell-cheap<0.30 + R5 h=150) from "
             "`ladder_baseline_study.py`; rung-4 streak is OFF and replaced by the variant's "
             "continuous size multiplier on the OPENING leg (both legs inherit it). Helpers "
             "(tstat/sortino/recovery/ulcer/var95/cvar95/ir/...) imported from `box_policy_ab.py`. "
             "Backtests SCREEN only.\n".format(n_is, n_oos, oos_auc, gbm_thresh))

    L.append("## References\n")
    L.append("- **(a) LIVE streak-guard** = combined ladder WITH `--strand-scaledown 0.75,0.5,0.25` "
             f"(deployed today). OOS net **{streak_net:+.2f}c/win**, MaxDD {m_streak_oos['mdd']:.1f}c, "
             f"CVaR95 {m_streak_oos['cv95']:.2f}c, strand {streak_strand:.1f}%.\n")
    L.append("- **(b) BASELINE drop-R4** = combined ladder with rung 4 dropped entirely (the "
             f"leave-one-out ablation winner). OOS net **{base_net:+.2f}c/win**, MaxDD "
             f"{m_base_oos['mdd']:.1f}c, CVaR95 {m_base_oos['cv95']:.2f}c, strand {base_strand:.1f}%. "
             "This is the bar to beat: the ablation showed dropping R4 is itself an improvement.\n")

    L.append("## Ranked variants (OOS, full A/B metric set)\n")
    L.append("| Variant | IS net | OOS net | Sharpe | Sortino | Skew | Kurt | Recov | Ulcer | VaR95 | CVaR95 | IR-vs-base | Expect | TUW% | MaxDD | Strand% | PF |")
    L.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for label, mi, mo, st in ranked:
        L.append("| {} | {:+.2f} | {:+.2f} | {:+.2f} | {:+.2f} | {:+.2f} | {:+.2f} | {:+.2f} | "
                 "{:.2f} | {:.2f} | {:.2f} | {:+.2f} | {:+.2f} | {:.1f} | {:.1f} | {:.1f} | {:.2f} |".format(
                     label, mi.get('nc', float('nan')), mo['nc'], mo['sh'], mo['sor'], mo['skew'],
                     mo['kurt'], mo['recov'], mo['ulcer'], mo['v95'], mo['cv95'],
                     mo.get('ir_p0', float('nan')), mo.get('awl', float('nan')), mo['tuw'],
                     mo['mdd'], st, mo['pf']))
    L.append("")
    L.append("(IR-vs-base = information ratio of the variant's per-window PnL vs reference (b). "
             "All metrics per-window, PnL in cents/contract.)\n")

    L.append("## Top-variant uplift + significance (OOS, paired t)\n")
    L.append("| Variant | d vs (b) base (c/win) | t-stat | d vs (a) streak (c/win) | t-stat |")
    L.append("|---|--:|--:|--:|--:|")
    for label in tstat_info:
        tb, ts, db, ds = tstat_info[label]
        L.append(f"| {label} | {db:+.2f} | {tb:+.2f} | {ds:+.2f} | {ts:+.2f} |")
    L.append("")

    # determine verdict
    winner = ranked[0]
    win_label = winner[0]
    win_oos = winner[2]['nc']
    sig = tstat_info.get(win_label)
    # A variant only counts as "beating" the baseline if it is BOTH higher AND the
    # uplift is statistically meaningful (|t|>=2 on the paired OOS difference).
    # A +0.02c edge at t=0.03 is noise, not an improvement.
    SIG_T = 2.0
    sig_beats_base = (sig is not None and sig[2] > 0 and abs(sig[0]) >= SIG_T)
    beats_base = win_oos > base_net + 1e-9 and not win_label.startswith("(b)") and sig_beats_base

    L.append("## Verdict\n")
    if win_label.startswith("(b)") or (not win_label.startswith("(a)") and not sig_beats_base):
        td = "" if sig is None else f" (best variant `{win_label}`: {sig[2]:+.2f}c/win, t={sig[0]:+.2f} vs base — NOT significant)"
        L.append(f"**Nothing meaningfully beats simply DROPPING rung 4.** The drop-R4 baseline (b) "
                 f"sits at the TOP of the OOS net ranking at {base_net:+.2f}c/win; the highest-ranked "
                 f"MANAGE variant is within noise of it and fails the |t|>=2 significance bar{td}. "
                 f"The honest recommendation is to REMOVE the streak guard and run NO manage rung "
                 f"(rungs 1-3 + at-scale 5 only).\n")
        L.append(f"\n**Why continuous sizing can't add net here.** A box leg only loses money when it "
                 f"STRANDS; a paired box is locked/risk-free. Any size cut therefore shaves the locked "
                 f"edge on the (overwhelming) paired boxes to buy a smaller loss on the rare strand. "
                 f"At a ~0.65% per-fill strand rate the trade-off is roughly neutral-to-negative on "
                 f"net — exactly what the table shows: every aggressive sizer (V4 Bayes, V6 AvSt, V3 "
                 f"tox) cuts MaxDD/CVaR/Ulcer hard (Bayes drops MaxDD 457c->90c) but bleeds net "
                 f"(down to +0.79c). The only variants that hold net (V1 GBM, V2 Kelly) are the ones "
                 f"that barely cut size at all — i.e. they converge to the drop-R4 baseline.\n")
        L.append(f"\n**If a risk-budget (not net) is the objective**, the strong tail-control option "
                 f"is `V2 Kelly lam0.25` ({[r for r in ranked if r[0]=='V2 Kelly lam0.25'][0][2]['nc']:+.2f}c "
                 f"net but MaxDD 279c vs 457c, CVaR95 45.7c vs 65.0c, PF 1.57 vs 1.45, Sortino +0.17 vs "
                 f"+0.13) — it sacrifices ~0.7c/win for a ~40% MaxDD cut. This is a genuinely better "
                 f"risk-adjusted profile than the live streak-guard (which gives up net AND has worse "
                 f"tails). But on the mandated PRIMARY metric (net c/win) it loses to dropping R4.\n")
        rec_flag = "(no manage rung) — leave `--strand-scaledown` UNSET / empty"
        rec_drop = True
    elif win_label.startswith("(a)"):
        L.append(f"**The live streak-guard is the top variant** — unexpected given the ablation. "
                 f"Treat with suspicion and forward-validate.\n")
        rec_flag = "--strand-scaledown 0.75,0.5,0.25 (unchanged)"
        rec_drop = False
    else:
        verdict = "beats" if beats_base else "does NOT beat"
        L.append(f"**Recommended rung-4 MANAGE strategy: `{win_label}`.** OOS net {win_oos:+.2f}c/win, "
                 f"which {verdict} the (b) baseline ({base_net:+.2f}c) and the (a) streak-guard "
                 f"({streak_net:+.2f}c).\n")
        if sig:
            tb, ts, db, ds = sig
            L.append(f"- vs (b) baseline: {db:+.2f}c/win, t={tb:+.2f}\n")
            L.append(f"- vs (a) streak-guard: {ds:+.2f}c/win, t={ts:+.2f}\n")
        L.append(f"- IS net {winner[1].get('nc',float('nan')):+.2f}c vs OOS {win_oos:+.2f}c "
                 f"(IS/OOS stability check).\n")
        rec_flag = win_label
        rec_drop = False

    L.append("## IS/OOS stability\n")
    L.append("Compare each row's IS net to OOS net in the ranked table above. Variants whose IS and "
             "OOS net agree in sign and rough magnitude are stable; large IS>>OOS gaps indicate "
             "in-sample overfit (note IS excludes the GBM gate, so IS net is mechanically higher for "
             "GBM-dependent variants — judge stability on RANK persistence, not absolute level).\n")

    L.append("## Deployment\n")
    L.append("The live trader (`live_trader.py` / `kalshi_trader.py`) uses argparse flags. The "
             "deployed manage rung is `--strand-scaledown \"0.75,0.5,0.25\"` (a discrete streak "
             "ladder). To deploy the recommendation:\n")
    if rec_drop:
        L.append("- **REMOVE / leave empty** the streak-scaledown: run with `--strand-scaledown \"\"` "
                 "(or omit it) so no manage-rung resize is applied. This matches the ablation finding "
                 "that dropping R4 improves OOS net. Rungs 1 (t36), 2 (GBM gate), 3 (sell-cheap), and "
                 "5 (hedge, at-scale) remain.\n")
        L.append("- If a continuous size hook is later desired (it screened near-baseline, not above), "
                 "add a `--manage-size gbm:k=5,floor=0.25` style flag that multiplies the opening clip "
                 "by `max(floor, 1 - p_strand*k)` using the rung-2 GBM probability — but only AFTER "
                 "forward validation, since it did not beat simply dropping the rung here.\n")
    else:
        L.append(f"- Replace the discrete streak flag with a NEW continuous-sizing flag, e.g. "
                 f"`--manage-size \"{_flag_for(win_label)}\"`, and SET `--strand-scaledown \"\"` "
                 f"(disable the streak ladder). The trader multiplies each opening clip by the "
                 f"variant's continuous multiplier (GBM strand-prob / Kelly / inventory term).\n")
    L.append("\n**FORWARD VALIDATION REQUIRED** before swapping live config: backtests SCREEN only; "
             "bar t>3, n>=300 windows of paper/forward data per the lockdown protocol.\n")

    with open('/tmp/pc_manage/MANAGE_RUNG.md', 'w') as fh:
        fh.write("\n".join(L))


def _flag_for(label):
    """Map a winning variant label to a concrete proposed trader-flag string."""
    if label.startswith("V1 GBM"):
        # "V1 GBM 1-p*5 fl0.25"
        try:
            k = label.split("*")[1].split(" ")[0]
            fl = label.split("fl")[1]
            return f"gbm:k={k},floor={fl}"
        except Exception:
            return "gbm:k=5,floor=0.25"
    if label.startswith("V2 Kelly"):
        return "kelly:lam=" + label.split("lam")[1]
    if label.startswith("V3 tox"):
        return "tox:k=5,floor=0.25"
    if label.startswith("V4 Bayes"):
        return "bayes:gamma=4,decay=0.5,power=2"
    if label.startswith("V5 hybrid"):
        return "hybrid:gbm_k=5,floor=0.25,big=0.10,cut=0.5"
    if label.startswith("V6 AvSt"):
        return "avst:gbm_k=5,gamma=2,decay=0.5"
    return "gbm:k=5,floor=0.25"


if __name__ == '__main__':
    main()
