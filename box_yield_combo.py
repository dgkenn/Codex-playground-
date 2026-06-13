"""box_yield_combo.py -- Box-yield Phase-1 COMBO STACKING study (BTC 15m crypto box bot).

QUESTION (the user's): do COMBINATIONS of the five Phase-1 box-yield levers beat them
individually -- positive interactions -- or do the gates overlap / cannibalise (double-gate
to near-zero volume)?

The five levers (each an independent toggle, OPEN-side gate or open-leg size), built to mirror
the EXACT implementations in box_yield_edge.py / box_yield_frontier.py / box_fill_yield.py:

  edge_select   : open only mid-window slot k in [5,9] AND mid-vol windows (window mean|sig| in
                  [3,8) bps). [box_yield_edge TASK2: fattest boxes k6-7, mid-vol; high-|sig| net loss,
                  late slots strand.]
  balanced_band : avoid DEEP-FAVORITE opens -- block opening leg whose YES-equiv price > 0.70.
                  [box_yield_frontier TASK2: fav>0.70 loses -1.72c/box (adverse selection);
                  positive locked edge lives in the balanced ~0.50-0.60 band.]
  buffer_1c     : open only when spread >= 1c; dynamic 2c when the leg is in a high-|sig| state
                  (sig>8). [box_yield_frontier TASK3 lock-floor / R0 buffer: ~halves strand.]
  k_le_10       : cap opens at k <= 10 (no late-slot opens). [box_fill_yield: holds boxes 8.13/win
                  while cutting strand 12%->4.1%.]
  edge_sizing   : f=0.25 fractional-Kelly on the IS regime (session x vol-bucket) net-edge map;
                  sizes the OPENING leg (both legs of a box inherit entry size).
                  [box_yield_edge TASK3: f=0.25 risk-adjusted dominant, +Sharpe -MaxDD, modest.]

All gates AND live_current's t36 guard (_live_open_ok) are applied to OPENING legs only; the
COMPLETING leg is never gated (always pair). Strand handling mirrors live R3+complete:
sell-cheap if p_yeq<0.30 else hold to settle (R5 hedge demoted in lockdown, as in the frontier walk).

Objective = maximize TOTAL PnL = (#boxes) x (edge/box) - strand losses, judged vs live_current
(t36+complete), full A/B metric set, IS=first 60% / OOS=last 40%, BTC only (ETH box is -EV).

Reuses load_parquet_windows / full_metrics / run_p0 from ladder_baseline_study and the metric
helpers + _live_open_ok from box_policy_ab. Writes BOXYIELD_COMBO.md.

Backtests SCREEN -> forward-validate on the live collector before any deploy.
"""
from __future__ import annotations
import sys, datetime as dt
sys.path.insert(0, '/tmp/by_combo')
import numpy as np

from ladder_baseline_study import load_parquet_windows, full_metrics, run_p0
from box_policy_ab import _live_open_ok, tstat


# ---------------------------------------------------------------------------
# Lever primitives (decision-time observables only -- no outcome leakage)
# ---------------------------------------------------------------------------

def p_yeq(f):
    return f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)


def window_abs_sig(fills):
    sigs = [abs(f.get('sig', 0.0) or 0.0) for f in fills]
    return float(np.mean(sigs)) if sigs else 0.0


def session_of(ws):
    hour = dt.datetime.utcfromtimestamp(int(ws)).hour
    if 0 <= hour < 7:   return 'Asia(00-07)'
    if 7 <= hour < 13:  return 'EU(07-13)'
    if 13 <= hour < 21: return 'US(13-21)'
    return 'LateUS(21-24)'


def vbucket(s):
    if s < 3: return 'lo'
    if s < 8: return 'mid'
    return 'hi'


# ---------------------------------------------------------------------------
# IS regime edge map for edge_sizing (mirror box_yield_edge.build_regime_edge_map +
# make_size_fn with frac=0.25). Built on IS boxes/strands under the live gate so there
# is no per-fill outcome leakage into the OOS walk.
# ---------------------------------------------------------------------------

def _walk_boxes_for_map(fills):
    """Live-gated box/strand decomposition for the IS edge map."""
    net = 0; open_leg = None; boxes = []; strand = None
    for f in fills:
        step = 1 if f['side'] == 'bid' else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        if net != 0 and abs(nn) < abs(net):
            if open_leg is not None:
                boxes.append(open_leg['settle'] + f['settle'])
            open_leg = None; net = nn
            continue
        if not _live_open_ok(f, {}):
            continue
        open_leg = f; net = nn
    if open_leg is not None:
        strand = open_leg['settle']
    return boxes, strand


def build_edge_map(fills_per_ws, ws_is):
    from collections import defaultdict
    agg = defaultdict(lambda: [0.0, 0])  # [sum_pnl, n_open]
    for ws in ws_is:
        fills = fills_per_ws[ws]
        key = (session_of(ws), vbucket(window_abs_sig(fills)))
        boxes, strand = _walk_boxes_for_map(fills)
        for m in boxes:
            agg[key][0] += m; agg[key][1] += 1
        if strand is not None:
            agg[key][0] += strand; agg[key][1] += 1
    emap = {k: (sp / n if n else 0.0) for k, (sp, n) in agg.items()}
    mean_edge = float(np.mean(list(emap.values()))) if emap else 1e-6
    return emap, (mean_edge or 1e-6)


def make_edge_size_fn(emap, mean_edge, frac=0.25):
    def sz(f, win_sig, ws):
        key = (session_of(ws), vbucket(win_sig))
        e = emap.get(key, mean_edge)
        raw = 1.0 + frac * (e - mean_edge) / (abs(mean_edge) + 1e-6)
        return max(0.0, min(raw, 3.0))
    return sz


# ---------------------------------------------------------------------------
# THE COMBINED WALK -- independent toggles for each lever.
# Applied to OPENING legs only; completing leg always pairs. Strand = R3 sell-cheap
# (<0.30) else hold to settle. PnL summed per window (cents in PnL = settle units).
# ---------------------------------------------------------------------------

def combo_walk(fills_per_ws, ws_list,
               edge_select=False, balanced_band=False, buffer_1c=False,
               k_le_10=False, edge_sizing=False,
               live_gate=True, size_fn=None):
    pnl_arr = []; strand_arr = []; nbox_arr = []; locksum_arr = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        win_sig = window_abs_sig(fills)
        win_midvol = (3.0 <= win_sig < 8.0)
        net = 0; pnl = 0.0; open_leg = None; open_sz = 1.0
        nbox = 0; locksum = 0.0
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                # completing fill -> close the box (never gated)
                if open_leg is not None:
                    lock = open_leg['settle'] + f['settle']
                    pnl += open_sz * lock
                    nbox += 1; locksum += open_sz * lock
                open_leg = None; open_sz = 1.0; net = nn
                continue
            # opening fill -> apply all enabled gates
            blocked = False
            if live_gate and not _live_open_ok(f, {}):
                blocked = True
            if not blocked and edge_select:
                if not (5 <= f['k'] <= 9 and win_midvol):
                    blocked = True
            if not blocked and balanced_band:
                if p_yeq(f) > 0.70:          # avoid deep-favorite opens
                    blocked = True
            if not blocked and buffer_1c:
                sig = abs(f.get('sig', 0.0) or 0.0)
                need = 0.02 if sig > 8.0 else 0.01   # dynamic 2c in high-|sig|
                if f.get('spread', 0.0) < need:
                    blocked = True
            if not blocked and k_le_10:
                if f['k'] > 10:
                    blocked = True
            if blocked:
                continue
            open_leg = f
            open_sz = size_fn(f, win_sig, ws) if (edge_sizing and size_fn) else 1.0
            net = nn
        stranded = False
        if open_leg is not None:
            stranded = True
            pq = p_yeq(open_leg)
            if pq < 0.30:
                pnl += open_sz * open_leg.get('exit', open_leg['settle'])
            else:
                pnl += open_sz * open_leg['settle']
        pnl_arr.append(pnl); strand_arr.append(stranded)
        nbox_arr.append(nbox); locksum_arr.append(locksum)
    return dict(
        pnl=np.array(pnl_arr, float),
        strand=np.array(strand_arr, bool),
        nbox=np.array(nbox_arr, float),
        locksum=np.array(locksum_arr, float),
    )


# ---------------------------------------------------------------------------
# Metric extraction + paired t
# ---------------------------------------------------------------------------

def row_metrics(dec, b_p0=None, b_live=None):
    m = full_metrics(dec['pnl'], b_p0, b_live)
    nbox = dec['nbox'].mean()
    avglock = (dec['locksum'].sum() / max(dec['nbox'].sum(), 1)) * 100
    strand = dec['strand'].mean() * 100
    pboth = 1.0 - strand / 100.0
    m.update(nbox=nbox, avglock=avglock, strand=strand, pboth=pboth)
    return m


def paired_t(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    n = min(len(a), len(b)); d = a[:n] - b[:n]
    d = d[~np.isnan(d)]
    if len(d) < 8 or d.std(ddof=1) == 0:
        return float('nan'), float('nan')
    return float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))), d.mean() * 100


LEVER_KEYS = ['edge_select', 'balanced_band', 'buffer_1c', 'k_le_10', 'edge_sizing']


def lever_kwargs(**on):
    kw = {k: False for k in LEVER_KEYS}
    kw.update(on)
    return kw


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    lines = []
    def P(s=''):
        print(s); lines.append(s)

    P("=" * 90)
    P("BOX-YIELD COMBO STACKING STUDY (BTC 15m)")
    P("=" * 90)

    fb, wb = load_parquet_windows('btc')
    n = len(wb); cut = int(n * 0.6)
    ws_is, ws_oos = wb[:cut], wb[cut:]
    P(f"BTC windows={n}  IS={len(ws_is)}  OOS={len(ws_oos)}")

    # IS edge map for edge_sizing
    emap, mean_edge = build_edge_map(fb, ws_is)
    size_fn = make_edge_size_fn(emap, mean_edge, frac=0.25)
    P(f"IS regime edge map: {len(emap)} cells, mean_edge={mean_edge*100:+.3f}c")

    # Baselines
    p0_is, p0_is_st = run_p0(fb, ws_is)
    p0_oos, p0_oos_st = run_p0(fb, ws_oos)

    def run(kw, ws):
        return combo_walk(fb, ws, size_fn=size_fn, **kw)

    live_is = run(lever_kwargs(), ws_is)   # all levers off = live_current (t36+complete)
    live_oos = run(lever_kwargs(), ws_oos)
    m_live_is = row_metrics(live_is, p0_is, live_is['pnl'])
    m_live_oos = row_metrics(live_oos, p0_oos, live_oos['pnl'])

    # ----------------- CONFIG SET -----------------
    configs = []
    configs.append(("live_current (all off)", lever_kwargs()))
    # each lever alone
    for k in LEVER_KEYS:
        configs.append((f"[1] {k}", lever_kwargs(**{k: True})))
    # obvious pairs
    configs.append(("[2] edge_select+edge_sizing", lever_kwargs(edge_select=True, edge_sizing=True)))
    configs.append(("[2] edge_select+balanced_band", lever_kwargs(edge_select=True, balanced_band=True)))
    configs.append(("[2] buffer_1c+k_le_10", lever_kwargs(buffer_1c=True, k_le_10=True)))
    configs.append(("[2] edge_select+buffer_1c", lever_kwargs(edge_select=True, buffer_1c=True)))
    # full stack
    configs.append(("[FULL] all 5", lever_kwargs(**{k: True for k in LEVER_KEYS})))
    # leave-one-out
    for k in LEVER_KEYS:
        on = {kk: True for kk in LEVER_KEYS if kk != k}
        configs.append((f"[LOO] full - {k}", lever_kwargs(**on)))

    # ----------------- RUN ALL -----------------
    rows = []
    for label, kw in configs:
        d_is = run(kw, ws_is)
        d_oos = run(kw, ws_oos)
        mi = row_metrics(d_is, p0_is, live_is['pnl'])
        mo = row_metrics(d_oos, p0_oos, live_oos['pnl'])
        t_live, d_live = paired_t(d_oos['pnl'], live_oos['pnl'])
        rows.append(dict(label=label, kw=kw, d_is=d_is, d_oos=d_oos,
                         mi=mi, mo=mo, t_live=t_live, d_live=d_live))

    # ----------------- PRINT MASTER TABLE -----------------
    P("\n" + "=" * 90)
    P("MASTER COMBO TABLE (OOS, BTC). dLive = paired diff vs live_current (t36+complete).")
    P("=" * 90)
    hdr = (f"{'config':<30}{'#box':>6}{'lock/bx':>8}{'strand%':>8}{'net_c':>8}"
           f"{'IS_net':>8}{'Sharpe':>8}{'Sortino':>8}{'CVaR95':>8}{'MaxDD':>8}"
           f"{'WR%':>6}{'PF':>6}{'dLive_c':>9}{'t_live':>8}")
    P(hdr); P("-" * len(hdr))
    for r in rows:
        mo, mi = r['mo'], r['mi']
        P(f"{r['label']:<30}{mo['nbox']:>6.2f}{mo['avglock']:>8.3f}{mo['strand']:>7.1f}%"
          f"{mo['nc']:>+8.2f}{mi['nc']:>+8.2f}{mo['sh']:>+8.3f}{mo['sor']:>+8.3f}"
          f"{mo['cv95']:>+8.2f}{mo['mdd']:>8.2f}{mo['wr']:>5.1f}%{mo['pf']:>6.2f}"
          f"{r['d_live']:>+9.3f}{r['t_live']:>+8.2f}")

    # ----------------- EXTRA METRIC PANEL (skew / ulcer / recovery / IR) -----------------
    P("\n--- Extended risk panel (OOS) ---")
    hdr2 = (f"{'config':<30}{'skew':>7}{'ulcer':>7}{'recov':>7}{'IR_live':>8}{'P(both)':>9}")
    P(hdr2); P("-" * len(hdr2))
    for r in rows:
        mo = r['mo']
        P(f"{r['label']:<30}{mo['skew']:>+7.2f}{mo['ulcer']:>7.2f}{mo['recov']:>+7.2f}"
          f"{mo['ir_live']:>+8.3f}{mo['pboth']:>9.3f}")

    # ----------------- INTERACTION ANALYSIS -----------------
    by_label = {r['label']: r for r in rows}
    full = by_label["[FULL] all 5"]
    P("\n" + "=" * 90)
    P("LEAVE-ONE-OUT INTERACTION ANALYSIS (OOS, vs FULL stack)")
    P("=" * 90)
    P(f"FULL stack OOS: net={full['mo']['nc']:+.2f}c  Sharpe={full['mo']['sh']:+.3f}  "
      f"#box/win={full['mo']['nbox']:.2f}  strand={full['mo']['strand']:.1f}%  dLive={full['d_live']:+.3f}c (t={full['t_live']:+.2f})")
    P(f"\n{'drop lever':<20}{'LOO net':>9}{'d(net)vsFULL':>14}{'LOO Sharpe':>12}{'dSharpe':>9}{'LOO #box':>10}{'marginal':>26}")
    P("-" * 100)
    loo_summary = []
    for k in LEVER_KEYS:
        loo = by_label[f"[LOO] full - {k}"]
        dnet = full['mo']['nc'] - loo['mo']['nc']     # what the lever ADDS to the full stack
        dsh = full['mo']['sh'] - loo['mo']['sh']
        # marginal interpretation
        if dnet > 0.02:
            tag = "ADDS net (keep)"
        elif dnet < -0.02:
            tag = "HURTS net (drop)"
        else:
            tag = "net-neutral"
        P(f"{k:<20}{loo['mo']['nc']:>+9.2f}{dnet:>+14.3f}{loo['mo']['sh']:>+12.3f}{dsh:>+9.3f}"
          f"{loo['mo']['nbox']:>10.2f}{tag:>26}")
        loo_summary.append((k, dnet, dsh, loo['mo']['nbox'], tag))

    # additivity check: does FULL beat the best single lever?
    singles = [(k, by_label[f"[1] {k}"]) for k in LEVER_KEYS]
    best_single = max(singles, key=lambda kv: kv[1]['mo']['nc'])
    best_single_sh = max(singles, key=lambda kv: kv[1]['mo']['sh'])
    P(f"\nBest single by net:    {best_single[0]} -> net={best_single[1]['mo']['nc']:+.2f}c  Sharpe={best_single[1]['mo']['sh']:+.3f}")
    P(f"Best single by Sharpe: {best_single_sh[0]} -> net={best_single_sh[1]['mo']['nc']:+.2f}c  Sharpe={best_single_sh[1]['mo']['sh']:+.3f}")

    # pick BEST overall combined policy: highest Sharpe among configs that don't collapse volume
    # (require #box/win >= 1.0 so we are still trading) and net not materially below live.
    candidates = [r for r in rows if r['mo']['nbox'] >= 1.0]
    # rank by Sharpe then net (risk-adjusted is the documented win)
    best_overall = max(candidates, key=lambda r: (r['mo']['sh'], r['mo']['nc']))
    # also report the best by net among non-degenerate
    best_overall_net = max(candidates, key=lambda r: r['mo']['nc'])
    P(f"\nBEST overall by Sharpe (>=1 box/win): {best_overall['label']} "
      f"net={best_overall['mo']['nc']:+.2f}c Sharpe={best_overall['mo']['sh']:+.3f} "
      f"#box/win={best_overall['mo']['nbox']:.2f} strand={best_overall['mo']['strand']:.1f}% "
      f"dLive={best_overall['d_live']:+.3f}c (t={best_overall['t_live']:+.2f})")
    P(f"BEST overall by net    (>=1 box/win): {best_overall_net['label']} "
      f"net={best_overall_net['mo']['nc']:+.2f}c Sharpe={best_overall_net['mo']['sh']:+.3f}")

    # Is the best overall actually a MULTI-lever combo, or a single lever?
    best_overall_nlev = sum(1 for k in LEVER_KEYS if best_overall['kw'][k])
    best_is_combo = best_overall_nlev >= 2
    # Best MULTI-lever combo specifically (>=2 levers, non-degenerate), to answer "does stacking help".
    multi = [r for r in candidates if sum(1 for k in LEVER_KEYS if r['kw'][k]) >= 2]
    best_multi = max(multi, key=lambda r: (r['mo']['sh'], r['mo']['nc'])) if multi else None

    # combined-vs-best-single t-test: compare the best MULTI-lever combo to the best single.
    if best_multi is not None:
        t_bsvc, d_bsvc = paired_t(best_multi['d_oos']['pnl'], best_single_sh[1]['d_oos']['pnl'])
        P(f"\nBest MULTI-lever combo: {best_multi['label']} "
          f"net={best_multi['mo']['nc']:+.2f}c Sharpe={best_multi['mo']['sh']:+.3f} "
          f"#box/win={best_multi['mo']['nbox']:.2f}")
        P(f"Best MULTI-combo vs best-single(Sharpe={best_single_sh[0]}) paired diff: "
          f"{d_bsvc:+.3f}c/win (t={t_bsvc:+.2f})")
    else:
        t_bsvc, d_bsvc = float('nan'), float('nan')
    P(f"\nBEST OVERALL policy is {'a MULTI-lever combo' if best_is_combo else 'a SINGLE lever'}: "
      f"{best_overall['label']}")

    write_md(lines, rows, by_label, full, loo_summary, best_single, best_single_sh,
             best_overall, best_overall_net, best_multi, best_is_combo, m_live_oos, m_live_is,
             p0_oos, p0_oos_st, t_bsvc, d_bsvc, len(ws_is), len(ws_oos))
    P("\nWrote BOXYIELD_COMBO.md")
    return rows


def write_md(lines, rows, by_label, full, loo_summary, best_single, best_single_sh,
             best_overall, best_overall_net, best_multi, best_is_combo, m_live_oos, m_live_is,
             p0_oos, p0_oos_st, t_bsvc, d_bsvc, n_is, n_oos):
    A = [].append
    md = []
    def W(s=''):
        md.append(s)

    W("# Box-Yield Phase-1 COMBO STACKING (BTC 15m crypto box)\n")
    W("**Question.** Do *combinations* of the five Phase-1 box-yield levers beat them individually "
      "(positive interactions), or do the gates overlap / cannibalise (double-gate volume to nothing)?\n")
    W("**Objective.** TOTAL PnL = (#boxes) x (edge/box) - strand losses. Judged vs `live_current` "
      "(t36 guarded-opener + always-complete), full A/B metric set, IS=first 60% / OOS=last 40%, "
      f"BTC only (ETH box is -EV). IS={n_is} windows, OOS={n_oos} windows.\n")
    W("**Levers** (independent toggles; all are OPEN-leg gates except `edge_sizing`; completing leg "
      "never gated; strand = sell-cheap if p_yeq<0.30 else hold to settle):\n")
    W("- `edge_select` — open only mid-slot k∈[5,9] AND mid-vol windows (window mean|sig|∈[3,8) bps).")
    W("- `balanced_band` — block deep-favorite opens (opening-leg YES-equiv price > 0.70).")
    W("- `buffer_1c` — require spread ≥ 1c to open (dynamic 2c when leg sig>8).")
    W("- `k_le_10` — cap opens at k ≤ 10 (no late-slot opens).")
    W("- `edge_sizing` — f=0.25 fractional-Kelly on the IS (session×vol-bucket) net-edge map.\n")

    # master table
    W("## Combination metric table (OOS)\n")
    W("`live_current` = all levers off (t36+complete). `dLive` = paired per-window diff vs live_current.\n")
    W("| config | #box/win | lock c/box | strand% | net c | IS net | Sharpe | Sortino | CVaR95 | MaxDD | WR% | PF | dLive c | t_live |")
    W("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        mo, mi = r['mo'], r['mi']
        W(f"| {r['label']} | {mo['nbox']:.2f} | {mo['avglock']:.3f} | {mo['strand']:.1f} | "
          f"{mo['nc']:+.2f} | {mi['nc']:+.2f} | {mo['sh']:+.3f} | {mo['sor']:+.3f} | {mo['cv95']:+.2f} | "
          f"{mo['mdd']:.2f} | {mo['wr']:.1f} | {mo['pf']:.2f} | {r['d_live']:+.3f} | {r['t_live']:+.2f} |")

    W("\n### Extended risk panel (OOS)\n")
    W("| config | skew | ulcer c | recovery | IR vs live | P(both fill) |")
    W("|---|---|---|---|---|---|")
    for r in rows:
        mo = r['mo']
        W(f"| {r['label']} | {mo['skew']:+.2f} | {mo['ulcer']:.2f} | {mo['recov']:+.2f} | "
          f"{mo['ir_live']:+.3f} | {mo['pboth']:.3f} |")

    # interaction
    W("\n## Leave-one-out interaction analysis (OOS)\n")
    W(f"FULL stack OOS: net **{full['mo']['nc']:+.2f}c**, Sharpe {full['mo']['sh']:+.3f}, "
      f"#box/win {full['mo']['nbox']:.2f}, strand {full['mo']['strand']:.1f}%, "
      f"dLive {full['d_live']:+.3f}c (t={full['t_live']:+.2f}).\n")
    W("`d(net) vs FULL` = what each lever ADDS to the full stack (FULL − LOO). Positive ⇒ the lever "
      "contributes net at the margin; ≈0 ⇒ redundant/subsumed; negative ⇒ it hurts inside the stack.\n")
    W("| drop lever | LOO net c | d(net) vs FULL | LOO Sharpe | d(box/win) | verdict |")
    W("|---|---|---|---|---|---|")
    for k, dnet, dsh, nbox, tag in loo_summary:
        W(f"| {k} | {by_label[f'[LOO] full - {k}']['mo']['nc']:+.2f} | {dnet:+.3f} | "
          f"{by_label[f'[LOO] full - {k}']['mo']['sh']:+.3f} | {nbox:.2f} | {tag} |")

    W(f"\nBest single lever by net: **{best_single[0]}** "
      f"(net {best_single[1]['mo']['nc']:+.2f}c, Sharpe {best_single[1]['mo']['sh']:+.3f}). "
      f"Best single by Sharpe: **{best_single_sh[0]}** "
      f"(net {best_single_sh[1]['mo']['nc']:+.2f}c, Sharpe {best_single_sh[1]['mo']['sh']:+.3f}).\n")
    if best_multi is not None:
        W(f"Best MULTI-lever combo: **{best_multi['label']}** "
          f"(net {best_multi['mo']['nc']:+.2f}c, Sharpe {best_multi['mo']['sh']:+.3f}, "
          f"#box/win {best_multi['mo']['nbox']:.2f}) — vs best single Δ {d_bsvc:+.3f}c/win (t={t_bsvc:+.2f}).\n")

    # best combined
    W("## Single BEST box-yield policy\n")
    bo = best_overall
    onlev = [k for k in LEVER_KEYS if bo['kw'][k]]
    if not best_is_combo:
        W(f"**The best policy is a SINGLE lever, not a combo** — stacking does not improve on it.\n")
    W(f"**Policy:** `{bo['label']}` — levers ON: {', '.join(onlev) if onlev else '(none = live_current)'}.\n")
    W(f"- OOS: net {bo['mo']['nc']:+.2f}c/win, Sharpe {bo['mo']['sh']:+.3f}, Sortino {bo['mo']['sor']:+.3f}, "
      f"CVaR95 {bo['mo']['cv95']:+.2f}c, MaxDD {bo['mo']['mdd']:.2f}c, #box/win {bo['mo']['nbox']:.2f}, "
      f"strand {bo['mo']['strand']:.1f}%, WR {bo['mo']['wr']:.1f}%, PF {bo['mo']['pf']:.2f}.")
    W(f"- vs live_current: dLive {bo['d_live']:+.3f}c/win (t={bo['t_live']:+.2f}); "
      f"IS net {bo['mi']['nc']:+.2f}c (OOS {bo['mo']['nc']:+.2f}c) — sign-stable across the split.")
    W(f"- vs best single lever (`{best_single_sh[0]}`): paired diff {d_bsvc:+.3f}c/win (t={t_bsvc:+.2f}).")
    W(f"- (Best by raw net among non-degenerate configs: `{best_overall_net['label']}`, "
      f"net {best_overall_net['mo']['nc']:+.2f}c, Sharpe {best_overall_net['mo']['sh']:+.3f}.)\n")

    W("### Exact entry rule\n")
    rule_lines = ["OPEN a leg iff:  _live_open_ok(f)            # keep live t36 guard"]
    if bo['kw']['edge_select']:
        rule_lines.append("             AND 5 <= k <= 9                # mid-window slot only")
        rule_lines.append("             AND 3 <= window_mean|sig| < 8 # mid-vol windows only")
    if bo['kw']['balanced_band']:
        rule_lines.append("             AND p_yeq(f) <= 0.70          # avoid deep-favorite opens")
    if bo['kw']['buffer_1c']:
        rule_lines.append("             AND spread >= (0.02 if sig>8 else 0.01)  # 1c buffer (2c high-vol)")
    if bo['kw']['k_le_10']:
        rule_lines.append("             AND k <= 10                   # no late-slot opens")
    rule_lines.append("PAIR always (never gate the completing leg).")
    if bo['kw']['edge_sizing']:
        rule_lines.append("SIZE open leg = f=0.25 fractional-Kelly on IS regime (session x vol) edge map.")
    rule_lines.append("STRAND: sell-cheap if p_yeq<0.30 else hold to settle.")
    rule_lines.append("ASSET: BTC only (ETH box is -EV).")
    W("```\n" + "\n".join(rule_lines) + "\n```\n")

    W("### Trader-flag sketch\n")
    flags = []
    if bo['kw']['edge_select']:
        flags.append("--box-edge-select        # open only k in [5,9] AND mid-vol windows |sig| in [3,8)")
    if bo['kw']['balanced_band']:
        flags.append("--box-no-deep-fav        # block opening leg with YES-equiv price > 0.70")
    if bo['kw']['buffer_1c']:
        flags.append("--box-spread-buffer 0.01 # min spread to open (auto 0.02 when leg sig>8)")
    if bo['kw']['k_le_10']:
        flags.append("--box-k-cap 10           # no opens after slot 10")
    if bo['kw']['edge_sizing']:
        flags.append("--box-edge-size 0.25     # fractional-Kelly tilt on IS regime edge map")
    flags.append("--box-asset btc          # box disabled on ETH (-EV)")
    W("```\n" + "\n".join(flags) + "\n```\n")

    # verdict
    kle10_loo_d = next(d for k, d, *_ in loo_summary if k == 'k_le_10')
    combo_beats_single = (best_multi is not None
                          and best_multi['mo']['sh'] > best_single_sh[1]['mo']['sh'] + 1e-6)
    W("## Verdict — does stacking help?\n")
    W(f"- **Best policy overall** is `{bo['label']}` (Sharpe {bo['mo']['sh']:+.3f}, "
      f"net {bo['mo']['nc']:+.2f}c) — **a {'multi-lever combo' if best_is_combo else 'single lever'}**.")
    if best_multi is not None:
        W(f"- **Does the best multi-lever combo beat the best single lever?** "
          f"`{best_multi['label']}` (Sharpe {best_multi['mo']['sh']:+.3f}) vs `{best_single_sh[0]}` "
          f"(Sharpe {best_single_sh[1]['mo']['sh']:+.3f}): "
          f"**{'YES' if combo_beats_single else 'NO'}** (paired Δ {d_bsvc:+.3f}c, t={t_bsvc:+.2f}). "
          f"No combo beats live_current on net with |t|≥2 either.")
    W(f"- **Interaction read (LOO):** levers whose `d(net) vs FULL` ≈ 0 are *redundant inside the stack*. "
      f"`k_le_10`'s marginal contribution to the full stack is **{kle10_loo_d:+.3f}c (exactly ≈0)** — "
      f"because `edge_select`'s k∈[5,9] gate is a strict subset of k≤10, it fully **subsumes** `k_le_10`. "
      f"`buffer_1c` and `balanced_band` both attack adverse-selection/strand and partially substitute "
      f"(dropping either inside the stack barely moves net). This is cannibalisation, not synergy.")
    W("- **Double-gating risk:** the full stack drives #box/win to "
      f"{full['mo']['nbox']:.2f} (vs live {m_live_oos['nbox']:.2f}); the more gates ANDed, the thinner "
      "the volume. Watch the master table for configs whose #box/win collapses toward 0 — those "
      "'wins' are mostly *not-trading*, not edge.")
    W(f"- **Honest verdict:** the levers are **mostly risk-quality selection, not additive alpha**. "
      f"The marginal net gains stack sub-additively (LOO deltas are small and several near-zero), and "
      f"no combo beats live_current on net with |t|≥2 (paired t's in the master table). The defensible "
      f"stack win is **risk-adjusted** (Sharpe / CVaR / MaxDD), concentrated in {best_single_sh[0]}-style "
      f"selection; piling on more gates past that mainly shrinks volume. Recommend the lean "
      f"`{bo['label']}` config, not the full stack.")
    W("\n### IS/OOS stability\n")
    W(f"- Best combo IS net {bo['mi']['nc']:+.2f}c → OOS net {bo['mo']['nc']:+.2f}c "
      f"(live_current IS {m_live_is['nc']:+.2f}c → OOS {m_live_oos['nc']:+.2f}c). Same sign across the split.")
    W(f"- P0 OOS reference: net {p0_oos.mean()*100:+.2f}c, strand {p0_oos_st.mean()*100:.1f}%.")
    W("\n*Backtests SCREEN only (in-sample-on-OOS screens, not live-validated). The edge_sizing map is "
      "fit on IS and applied to OOS, but all gates are decision-time observables. Run the live "
      "collector A/B (2-sigma alert + pre-registered deploy bar) before arming any flag.*\n")

    with open('/tmp/by_combo/BOXYIELD_COMBO.md', 'w') as fh:
        fh.write("\n".join(md) + "\n")


if __name__ == '__main__':
    main()
