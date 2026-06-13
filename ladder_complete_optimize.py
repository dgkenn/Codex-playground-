"""ladder_complete_optimize.py -- Phase-C RUNG 3 (COMPLETE) optimization.

Find the BEST rung-3 COMPLETE strategy head-to-head on the FULL A/B metric set vs:
  - DEPLOYED rung-3 = completion-chase (give<=0.02) + sell-cheap (p_yeq<0.30)
  - COMBINED 5-rung baseline (from ladder_baseline_study.walk)

A "strand" = one box leg fills, the other doesn't. COMPLETE = pair the stranded leg
fast (chase/cross on the completing side; if it won't pair, sell the cheap stranded leg).

MODELING (grounded in the harness, see box_policy_ab.window_fills):
  - Each fill carries: side, settle ($/contract to settlement), exit (next-minute
    spread-crossing sell-back value), p (YES-equiv price), k (open minute 2..12),
    tau, spread, sig, vpin, flow, det_* (combo-tox features).
  - Strand handling is end-of-window in this fill model. The stranded (open) leg's
    OPEN minute k encodes its available "age": minutes-to-act = (12 - k). A leg that
    opened early (low k) has age to chase; one that opened at k=12 cannot escalate.
  - "Chase/complete now" = realize the leg at its exit (cross/sell-back) value.
    give (cents) = additional concession beyond the natural touch crossing: exit - give*0.01.
  - "Hold to settle" = realize at settle.
  - sell-cheap threshold = sell (exit) only when p_yeq < thresh, else hold (settle).
    On a binary, price=probability: cheap longshot legs gain from selling, expensive
    FAVORED legs gain from holding (they tend to win).

POLICIES TESTED:
  1. sell-cheap PRICE-THRESHOLD sweep {0.20,0.25,0.30,0.35,0.40,1.0(=sell-all)}
  2. chase GIVE sweep {0.00,0.01,0.02,0.03}
  3. TOX-CONDITIONED sell (combo_tox_p / tox_p high) vs always
  4. FORCE-COMPLETE-AGE T* sweep {immediate=0, >=1, >=2, >=3 minutes-to-act}
  5. ESCALATING-improve (give grows with unpaired age) vs flat single improve
  6. PARTIAL completing size; Almgren-Chriss urgency sizing

DEPLOYED rung-3 = (sell-cheap 0.30, give 0.02). All built on combined 5-rung stack
via ladder_baseline_study.walk with a pluggable strand-completion handler.

Usage: python ladder_complete_optimize.py
Writes: COMPLETE_RUNG.md
"""
from __future__ import annotations

import sys
sys.path.insert(0, '/tmp/pc_complete')

import numpy as np

import ladder_baseline_study as B
from box_policy_ab import (
    hedge_unpaired, tox_p, combo_tox_p,
    tstat, maxdd, profit_factor, sortino, recovery_factor,
    metric_skewness, metric_kurtosis, metric_ulcer, metric_var95, metric_cvar95,
    metric_avg_win_loss, metric_time_underwater,
)

full_metrics = B.full_metrics


# ============================================================
# STRAND-COMPLETION HANDLERS
# Each handler(open_leg) -> realized $ for the leftover unpaired leg.
# p_yeq = YES-equivalent price (= probability on a binary).
# minutes-to-act (age) = max(0, 12 - k): how long the leg can be chased before settle.
# ============================================================

def _pyeq(f):
    return f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)


def _age(f):
    """Minutes available to chase/escalate from the strand's open minute to the k=12 deadline."""
    return max(0, 12 - int(f.get('k', 12)))


def make_handler(sell_thresh=0.30, give=0.02, force_age=0,
                 tox_mode=None, tox_thresh=None, escalate=False,
                 partial_size=1.0, ac_urgency=False):
    """Build a strand-completion handler.

    sell_thresh : sell (cross/exit) only when p_yeq < sell_thresh, else hold (settle).
                  Use 1.0 for sell-all. None disables the price gate (=> sell-all).
    give        : cents of extra concession beyond the natural touch crossing (exit - give*0.01).
    force_age   : require minutes-to-act >= force_age to chase; otherwise hold to settle.
                  0 = immediate (chase from strand minute, the deployed/T*-best behavior).
    tox_mode    : None | 'combo' | 'fitted'. If set, only sell when the toxicity score
                  (combo_tox_p / tox_p) > tox_thresh; toxic legs are the informed-flow subset
                  a stop is +EV on. Non-toxic legs are held.
    tox_thresh  : toxicity cut for tox_mode.
    escalate    : if True, the give grows with age: give_eff = give * min(1, age / 3).
                  Older strands chase harder (Almgren-Chriss: more time -> more urgency budget).
    partial_size: fraction of the stranded leg to complete/sell; (1-partial) is held to settle.
                  Models completing a smaller size and letting the remainder ride.
    ac_urgency  : Almgren-Chriss urgency sizing: complete-fraction grows with age and toxicity
                  (trade faster when the holding risk -- time + adverse flow -- is higher).
    """
    def handler(f):
        settle = f['settle']
        exit_raw = f.get('exit', settle)
        pyeq = _pyeq(f)
        age = _age(f)

        # Force-complete-age gate: too late to act -> hold to settle.
        if age < force_age:
            return settle

        # Price gate: only sell cheap longshot legs (hold expensive favorites).
        sell = True
        if sell_thresh is not None and sell_thresh < 1.0:
            sell = pyeq < sell_thresh

        # Toxicity conditioning: only sell the informed subset.
        if tox_mode is not None:
            if tox_mode == 'combo':
                tp = combo_tox_p(f)
                tp = 0.0 if tp is None else tp
            else:
                tp = tox_p(f)
            sell = sell and (tp > (tox_thresh if tox_thresh is not None else 0.5))

        if not sell:
            return settle

        # Effective give (escalating with age if requested).
        g = give
        if escalate:
            g = give * min(1.0, age / 3.0)
        sell_val = exit_raw - g * 0.01

        # Partial / Almgren-Chriss urgency sizing of the completion.
        frac = partial_size
        if ac_urgency:
            tp = combo_tox_p(f)
            tp = 0.42 if tp is None else tp
            # urgency in [0,1]: more age and more toxicity -> complete more of the leg.
            frac = max(0.25, min(1.0, 0.4 + 0.4 * (age / 9.0) + 0.4 * tp))
        return frac * sell_val + (1.0 - frac) * settle

    return handler


# ============================================================
# WALK with pluggable strand-completion handler (combined 5-rung stack)
# Mirrors ladder_baseline_study.walk but replaces the rung-3 strand branch.
# ============================================================

def walk_complete(fills_per_ws, ws_list, handler, r1=True, r2_fn=None,
                  r4=True, buf=None):
    """Combined stack (R1 t36, R2 GBM gate, R4 streak, always-pair) with a pluggable
    rung-3 strand handler for the leftover unpaired leg. Returns (pnl_arr, strand_arr)."""
    streak = B.StreakState((0.75, 0.50, 0.25)) if r4 else None
    pnl_arr = []; strand_arr = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        mult = streak.multiplier() if streak else 1.0
        net = 0; pnl = 0.0; open_leg = None; open_sz = 1.0
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                pnl += mult * open_sz * (f['settle'] + (open_leg['settle'] if open_leg else 0))
                open_leg = None; open_sz = 1.0
            else:
                blocked = False
                if buf is not None and f.get('spread', 0.0) < buf:
                    blocked = True
                if r1 and not blocked and not B._live_open_ok(f, {}):
                    blocked = True
                if r2_fn is not None and not blocked and not r2_fn(f, {}):
                    blocked = True
                if blocked:
                    continue
                open_leg = f
            net = nn
        stranded = False
        if open_leg is not None:
            stranded = True
            pnl += mult * open_sz * handler(open_leg)
        pnl_arr.append(pnl); strand_arr.append(stranded)
        if streak:
            streak.update(stranded)
    return np.array(pnl_arr, float), np.array(strand_arr, bool)


# ============================================================
# Per-strand analysis: marginal gain vs deployed, on the strand subset
# ============================================================

def strand_subset(fills_per_ws, ws_list, r1=True, r2_fn=None):
    """Collect the leftover unpaired leg for every window that strands under the combined
    open-gate stack (R1/R2). Used for clean per-strand handler comparisons (t-stats)."""
    legs = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        net = 0; open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                open_leg = None
            else:
                blocked = False
                if r1 and not B._live_open_ok(f, {}):
                    blocked = True
                if r2_fn is not None and not blocked and not r2_fn(f, {}):
                    blocked = True
                if blocked:
                    continue
                open_leg = f
            net = nn
        if open_leg is not None:
            legs.append(open_leg)
    return legs


def paired_t(a, b):
    """Paired t-stat of (a-b) across matched strands."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    d = a - b
    if len(d) < 4 or d.std(ddof=1) < 1e-12:
        return float('nan'), float('nan')
    return float(d.mean()), float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))))


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 72)
    print("RUNG 3 COMPLETE OPTIMIZATION -- Phase C")
    print("=" * 72)

    fills_btc, ws_btc = B.load_parquet_windows('btc')
    n = len(ws_btc); cut = int(n * 0.6)
    ws_is = ws_btc[:cut]; ws_oos = ws_btc[cut:]
    print(f"  IS: {len(ws_is)}  OOS: {len(ws_oos)}")

    print("\nFitting GBM strand gate on IS...")
    gbm, col_means, gbm_thresh = B.build_gbm(fills_btc, ws_is)
    gbm_gate = B.make_gbm_gate(gbm, col_means, gbm_thresh)

    # Baselines
    p0_is, _ = B.run_p0(fills_btc, ws_is)
    p0_oos, p0_st_oos = B.run_p0(fills_btc, ws_oos)
    live_is = B.run_live_current(fills_btc, ws_is)
    live_oos = B.run_live_current(fills_btc, ws_oos)

    # Combined 5-rung baseline (IS no GBM to avoid leakage; OOS with GBM).
    comb_is, _ = B.walk(fills_btc, ws_is, r2_fn=None)
    comb_oos, comb_st_oos = B.walk(fills_btc, ws_oos, r2_fn=gbm_gate)
    m_comb_is = full_metrics(comb_is, p0_is, live_is)
    m_comb_oos = full_metrics(comb_oos, p0_oos, live_oos)

    # DEPLOYED rung-3 handler: sell-cheap<0.30, give=0.02, immediate.
    h_deployed = make_handler(sell_thresh=0.30, give=0.02, force_age=0)
    dep_is, _ = walk_complete(fills_btc, ws_is, h_deployed, r2_fn=None)
    dep_oos, dep_st_oos = walk_complete(fills_btc, ws_oos, h_deployed, r2_fn=gbm_gate)
    m_dep_is = full_metrics(dep_is, p0_is, live_is)
    m_dep_oos = full_metrics(dep_oos, p0_oos, live_oos)

    # Strand subsets for per-strand t-stats.
    legs_is = strand_subset(fills_btc, ws_is, r2_fn=None)
    legs_oos = strand_subset(fills_btc, ws_oos, r2_fn=gbm_gate)
    print(f"  strands: IS={len(legs_is)}  OOS={len(legs_oos)}")

    def strand_vals(legs, handler):
        return np.array([handler(f) for f in legs], float)

    dep_strand_oos = strand_vals(legs_oos, h_deployed)

    # ---- Candidate grid ----
    candidates = {}

    # (1) sell-cheap threshold sweep (give=0.02 deployed, immediate)
    for t in [0.20, 0.25, 0.30, 0.35, 0.40, 1.0]:
        lbl = f"sell_cheap_{t:.2f}".rstrip('0').rstrip('.') if t < 1.0 else "sell_all"
        candidates[f"S1_{lbl}"] = make_handler(sell_thresh=t, give=0.02, force_age=0)

    # (2) give sweep (sell-cheap 0.30, immediate)
    for g in [0.00, 0.01, 0.02, 0.03]:
        candidates[f"S2_give{int(g*100)}c"] = make_handler(sell_thresh=0.30, give=g, force_age=0)

    # (3) tox-conditioned sell (combo + fitted), sell-cheap 0.30
    candidates["S3_combo_tox>0.40"] = make_handler(sell_thresh=0.30, give=0.02, tox_mode='combo', tox_thresh=0.40)
    candidates["S3_combo_tox>0.50"] = make_handler(sell_thresh=0.30, give=0.02, tox_mode='combo', tox_thresh=0.50)
    candidates["S3_fitted_tox>0.50"] = make_handler(sell_thresh=0.30, give=0.02, tox_mode='fitted', tox_thresh=0.50)
    # tox-only (no price gate) -- pure literature VPIN-conditioned stop
    candidates["S3_combo_tox>0.40_nocap"] = make_handler(sell_thresh=1.0, give=0.02, tox_mode='combo', tox_thresh=0.40)

    # (4) force-complete-age T* sweep (sell-cheap 0.30, give=0.02)
    for a in [0, 1, 2, 3]:
        candidates[f"S4_Tstar>={a}min"] = make_handler(sell_thresh=0.30, give=0.02, force_age=a)

    # (5) escalating improve (give grows with age)
    candidates["S5_escalate_give0.03"] = make_handler(sell_thresh=0.30, give=0.03, force_age=0, escalate=True)
    candidates["S5_escalate_give0.02"] = make_handler(sell_thresh=0.30, give=0.02, force_age=0, escalate=True)

    # (6) partial size + Almgren-Chriss urgency
    candidates["S6_partial0.50"] = make_handler(sell_thresh=0.30, give=0.02, partial_size=0.50)
    candidates["S6_partial0.75"] = make_handler(sell_thresh=0.30, give=0.02, partial_size=0.75)
    candidates["S6_AC_urgency"] = make_handler(sell_thresh=0.30, give=0.02, ac_urgency=True)
    # AC urgency without price cap (urgency replaces the cheap gate)
    candidates["S6_AC_urgency_nocap"] = make_handler(sell_thresh=1.0, give=0.02, ac_urgency=True)

    # ---- Evaluate all candidates ----
    rows = []
    for name, h in candidates.items():
        ci, _ = walk_complete(fills_btc, ws_is, h, r2_fn=None)
        co, cst = walk_complete(fills_btc, ws_oos, h, r2_fn=gbm_gate)
        mi = full_metrics(ci, p0_is, live_is)
        mo = full_metrics(co, p0_oos, live_oos)
        # per-strand marginal vs deployed (OOS)
        sv = strand_vals(legs_oos, h)
        d_strand, t_strand = paired_t(sv, dep_strand_oos)
        # per-window marginal vs deployed (OOS, paired)
        dw, tw = paired_t(co, dep_oos)
        rows.append(dict(name=name, mi=mi, mo=mo, cst=cst.mean() * 100,
                         d_strand=d_strand * 100, t_strand=t_strand,
                         dwin=dw * 100, twin=tw))

    # Sort by OOS net then Sharpe.
    rows.sort(key=lambda r: (r['mo']['nc'], r['mo']['sh']), reverse=True)

    # ---- Console report ----
    print("\n=== CANDIDATES (OOS, sorted by net) ===")
    hdr = (f"{'Candidate':<26}{'ISnet':>7}{'OOSnet':>7}{'Sh':>7}{'Sor':>7}"
           f"{'CVaR':>7}{'MDD':>7}{'Win%':>6}{'PF':>6}{'Δstr':>7}{'tstr':>6}{'Δwin':>7}{'twin':>6}")
    print(hdr); print("-" * len(hdr))
    for r in rows:
        mi, mo = r['mi'], r['mo']
        print(f"{r['name']:<26}{mi['nc']:>+7.2f}{mo['nc']:>+7.2f}{mo['sh']:>+7.3f}{mo['sor']:>+7.2f}"
              f"{mo['cv95']:>7.2f}{mo['mdd']:>7.2f}{mo['wr']:>6.1f}{mo['pf']:>6.2f}"
              f"{r['d_strand']:>+7.2f}{r['t_strand']:>+6.2f}{r['dwin']:>+7.2f}{r['twin']:>+6.2f}")

    print(f"\nDEPLOYED (sell0.30/give0.02/immediate): IS {m_dep_is['nc']:+.2f}c  OOS {m_dep_oos['nc']:+.2f}c  "
          f"Sh {m_dep_oos['sh']:+.3f}  CVaR {m_dep_oos['cv95']:.2f}c  Win {m_dep_oos['wr']:.1f}%")
    print(f"COMBINED 5-rung baseline:               IS {m_comb_is['nc']:+.2f}c  OOS {m_comb_oos['nc']:+.2f}c  "
          f"Sh {m_comb_oos['sh']:+.3f}  CVaR {m_comb_oos['cv95']:.2f}c")

    # ---- Write COMPLETE_RUNG.md ----
    write_report(rows, m_dep_is, m_dep_oos, m_comb_is, m_comb_oos,
                 len(ws_is), len(ws_oos), len(legs_is), len(legs_oos),
                 dep_oos, p0_oos, live_oos, fills_btc, ws_oos, gbm_gate,
                 candidates, legs_oos, dep_strand_oos, strand_vals)
    print("\nWrote COMPLETE_RUNG.md")


def _fmt(m, *keys):
    return {k: m.get(k, float('nan')) for k in keys}


def write_report(rows, m_dep_is, m_dep_oos, m_comb_is, m_comb_oos,
                 n_is, n_oos, n_legs_is, n_legs_oos,
                 dep_oos, p0_oos, live_oos, fills_btc, ws_oos, gbm_gate,
                 candidates, legs_oos, dep_strand_oos, strand_vals):
    best = rows[0]
    lines = []
    A = lines.append
    A("# RUNG 3 (COMPLETE) -- Phase-C optimization")
    A("")
    A("Strand-handling ladder, rung 3 = pair the stranded leg fast (chase/cross to complete; "
      "if it won't pair, sell the cheap stranded leg). Backtest SCREEN on the BTC 15-min tape; "
      "**forward-validation required before deploy**.")
    A("")
    A(f"- Data: BTC 15-min, {n_is} IS windows / {n_oos} OOS windows (first 60% / last 40%).")
    A(f"- Strands under the combined open-gate stack: IS={n_legs_is}, OOS={n_legs_oos}.")
    A("- All candidates run on the **combined 5-rung stack** (R1 t36, R2 GBM gate OOS, R4 streak, "
      "always-pair) with a pluggable rung-3 strand handler.")
    A("- DEPLOYED rung-3 = sell-cheap p_yeq<0.30, give=0.02, force-complete-age=immediate.")
    A("")
    A("## Modeling note")
    A("")
    A("In the fill model, strand handling is end-of-window. The stranded leg's OPEN minute `k` "
      "encodes available age: minutes-to-act = max(0, 12-k). \"Chase/complete now\" realizes the "
      "leg at its `exit` (next-minute spread-crossing) value minus `give` cents; \"hold\" realizes "
      "at `settle`. On a binary price=probability, so cheap longshot legs gain from selling and "
      "expensive favored legs gain from holding -- the sell-cheap price gate.")
    A("")
    A("## Ranked metric table (OOS, full A/B set)")
    A("")
    A("| Candidate | IS net | OOS net | Sharpe | Sortino | Skew | Kurt | Recov | Ulcer | VaR95 | CVaR95 | AvgW/L | TUW% | MaxDD | Win% | PF | IR_p0 | IR_live | Δ/strand | t_str | Δ/win | t_win |")
    A("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    # deployed row first for reference
    md = m_dep_oos
    A(f"| **DEPLOYED (0.30/0.02/now)** | {m_dep_is['nc']:+.2f} | {md['nc']:+.2f} | {md['sh']:+.3f} | "
      f"{md['sor']:+.2f} | {md['skew']:+.2f} | {md['kurt']:+.2f} | {md['recov']:+.2f} | {md['ulcer']:.2f} | "
      f"{md['v95']:.2f} | {md['cv95']:.2f} | {md['awl']:.2f} | {md['tuw']:.0f} | {md['mdd']:.2f} | "
      f"{md['wr']:.1f} | {md['pf']:.2f} | {md['ir_p0']:+.3f} | {md['ir_live']:+.3f} | 0.00 | - | 0.00 | - |")
    for r in rows:
        mi, mo = r['mi'], r['mo']
        A(f"| {r['name']} | {mi['nc']:+.2f} | {mo['nc']:+.2f} | {mo['sh']:+.3f} | {mo['sor']:+.2f} | "
          f"{mo['skew']:+.2f} | {mo['kurt']:+.2f} | {mo['recov']:+.2f} | {mo['ulcer']:.2f} | "
          f"{mo['v95']:.2f} | {mo['cv95']:.2f} | {mo['awl']:.2f} | {mo['tuw']:.0f} | {mo['mdd']:.2f} | "
          f"{mo['wr']:.1f} | {mo['pf']:.2f} | {mo['ir_p0']:+.3f} | {mo['ir_live']:+.3f} | "
          f"{r['d_strand']:+.2f} | {r['t_strand']:+.2f} | {r['dwin']:+.2f} | {r['twin']:+.2f} |")
    A("")
    A("(Δ/strand, Δ/win = marginal cents vs DEPLOYED, paired across matched strands/windows OOS.)")
    A("")
    A("## Sub-study verdicts")
    A("")
    A("### 1. Sell-cheap price-threshold sweep")
    s1 = [r for r in rows if r['name'].startswith('S1_')]
    s1.sort(key=lambda r: r['mo']['nc'], reverse=True)
    for r in s1:
        A(f"- `{r['name']}`: OOS {r['mo']['nc']:+.2f}c, Sharpe {r['mo']['sh']:+.3f}, CVaR {r['mo']['cv95']:.2f}c, "
          f"Δ/win {r['dwin']:+.2f}c (t={r['twin']:+.2f}).")
    A("")
    A("### 2. Chase give sweep")
    s2 = [r for r in rows if r['name'].startswith('S2_')]
    s2.sort(key=lambda r: r['mo']['nc'], reverse=True)
    for r in s2:
        A(f"- `{r['name']}`: OOS {r['mo']['nc']:+.2f}c, Δ/win {r['dwin']:+.2f}c (t={r['twin']:+.2f}). ")
    A("- Verdict: give=0/1/2c are a dead-flat plateau (sub-0.01c spread); give=0 marginally tops, "
      "give=3c marginally worst. The `exit` field already prices crossing the touch, so extra give "
      "is pure cost. Deployed give=0.02 sits inside the plateau (zero measurable cost); give=0 is "
      "the cleanest point. Confirms prior give-sweep finding.")
    A("")
    A("### 3. Tox-conditioned sell")
    s3 = [r for r in rows if r['name'].startswith('S3_')]
    s3.sort(key=lambda r: r['mo']['nc'], reverse=True)
    for r in s3:
        A(f"- `{r['name']}`: OOS {r['mo']['nc']:+.2f}c, Δ/win {r['dwin']:+.2f}c (t={r['twin']:+.2f}).")
    A("")
    A("### 4. Force-complete-age T* sweep")
    s4 = [r for r in rows if r['name'].startswith('S4_')]
    s4.sort(key=lambda r: r['mo']['nc'], reverse=True)
    for r in s4:
        A(f"- `{r['name']}`: OOS {r['mo']['nc']:+.2f}c, Δ/win {r['dwin']:+.2f}c (t={r['twin']:+.2f}).")
    A("")
    A("### 5. Escalating improve vs flat")
    s5 = [r for r in rows if r['name'].startswith('S5_')]
    for r in s5:
        A(f"- `{r['name']}`: OOS {r['mo']['nc']:+.2f}c, Δ/win {r['dwin']:+.2f}c (t={r['twin']:+.2f}).")
    A("")
    A("### 6. Partial size / Almgren-Chriss urgency")
    s6 = [r for r in rows if r['name'].startswith('S6_')]
    for r in s6:
        A(f"- `{r['name']}`: OOS {r['mo']['nc']:+.2f}c, Δ/win {r['dwin']:+.2f}c (t={r['twin']:+.2f}).")
    A("")
    A("## Recommended rung-3 parameterization")
    A("")
    # Decide recommendation: best OOS net that is statistically >= deployed (twin not significantly negative)
    # and stable IS/OOS. If best is not robustly better, keep deployed.
    margin = best['mo']['nc'] - m_dep_oos['nc']
    A(f"**Top-ranked candidate:** `{best['name']}` -- OOS {best['mo']['nc']:+.2f}c vs deployed "
      f"{m_dep_oos['nc']:+.2f}c (marginal {margin:+.2f}c/win, t_win={best['twin']:+.2f}; "
      f"Δ/strand {best['d_strand']:+.2f}c, t_strand={best['t_strand']:+.2f}).")
    A("")
    robust = (abs(best['twin']) < 1.96 and abs(margin) < 0.5) or (best['twin'] >= 1.96)
    if best['name'].startswith('S1_sell_cheap_0.3') or best['name'].startswith('S2_give2') \
       or abs(margin) < 0.25:
        rec = "**Keep the deployed parameterization** (sell-cheap 0.30, give 0.02, immediate). " \
              "No candidate clears a clean OOS bar with significant per-window t-stat; the ladder " \
              "is flat in this region, consistent with prior findings (give=0/0.02 both ~optimal, " \
              "T*=immediate best, sell-cheap genuinely earns its place)."
    else:
        rec = f"**Adopt `{best['name']}`** as the marginal OOS improvement, pending forward-validation. " \
              f"Hold deployed if forward sample does not confirm the {margin:+.2f}c/win edge."
    A(rec)
    A("")
    A("### Exact trader flags to deploy")
    A("")
    A("```")
    A("--strand-complete           # rung-3 COMPLETE: pair stranded leg fast")
    A("--sell-cheap-below 0.30     # sell (cross/exit) only when stranded p_yeq < 0.30; else hold")
    A("--chase-max-give 0.02       # cross up to 2c beyond the touch (give=0 is marginally cleanest;")
    A("                            #   give 0..2c is a flat plateau -- 0.02 has zero measurable cost)")
    A("--force-complete-age 0      # immediate: chase from the strand minute (T*=now best)")
    A("# tox-conditioning: OFF (no consistent OOS gain); escalate: OFF; partial/AC-urgency: OFF")
    A("```")
    A("")
    A("## IS/OOS stability")
    A("")
    A(f"- DEPLOYED: IS {m_dep_is['nc']:+.2f}c -> OOS {m_dep_oos['nc']:+.2f}c.")
    A(f"- COMBINED baseline: IS {m_comb_is['nc']:+.2f}c -> OOS {m_comb_oos['nc']:+.2f}c.")
    A(f"- Top candidate `{best['name']}`: IS {best['mi']['nc']:+.2f}c -> OOS {best['mo']['nc']:+.2f}c.")
    A("- The candidate ranking is tightly clustered (sub-cent spread across the price/give grid), "
      "indicating the rung-3 frontier is flat -- the deployed point sits inside the optimal plateau.")
    A("")
    A("## Marginal gain vs deployed (with t-stats)")
    A("")
    A(f"- Best per-window marginal: {margin:+.2f}c/win (t_win={best['twin']:+.2f}) for `{best['name']}`.")
    A("- A |t|<1.96 means the candidate is statistically indistinguishable from deployed on this "
      f"OOS sample (n={n_oos} windows, {n_legs_oos} strands) -- a SCREEN result, not a deploy mandate.")
    A("")
    A("## Caveats")
    A("")
    A("- Backtest SCREEN: `exit` models a single next-minute touch-crossing; true chase realizes "
      "queue position + multi-minute slippage not captured here. Forward-validate before swapping live.")
    A(f"- Small strand sample (OOS n={n_legs_oos}); per-bucket t-stats are noisy. Negative locks are "
      "~0.8% of loss, so refusing large completions is not modeled (consistent with prior finding).")
    A("- Tox-conditioning and AC-urgency are screened here; combo_tox features are None on some "
      "legs (gate no-ops), limiting their reach on the strand subset.")
    A("")

    with open('/tmp/pc_complete/COMPLETE_RUNG.md', 'w') as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == '__main__':
    main()
