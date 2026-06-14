"""pair_gate_study.py -- Find the ENTRY gate that cuts the maker-box STRAND rate to <5%
while keeping meaningful volume, then price the cheapest residual-strand disposal.

Context: the maker-box EDGE is real (+0.69c/box live, +0.37c backtest). The loss is STRANDS:
one leg fills, the other doesn't -> disposal cost -16 to -22c (hold) up to -83c (late force-cross).
Break-even needs strand rate < ~4.3%. We are at 16-33%.

Approach (tape replay; backtests SCREEN -- the fill model is optimistic on strands, so treat the
strand-rate REDUCTION as DIRECTIONAL, forward validation required):

1. STRAND-RATE BY ENTRY CONDITION: per OPENING fill, label whether the window it belongs to ended
   stranded (yes-count != no-count), and bucket strand probability vs entry-book conditions
   available at decision time: book imbalance / microprice divergence, min(depth) on both sides,
   spread, k-slot, |sig|, |flow|.
2. PAIR-GATE: open only when [balanced + both-sides depth + ...]; report strand-rate/volume/net.
3. DISPOSAL by timing: early-cross (exit at k+1) vs late-force (settle) vs hedge; recommend give-cap.
4. COMBINED projected net vs the -2c/box current, IS/OOS stability + Sharpe.

Writes PAIR_GATE.md.
"""
from __future__ import annotations
import sys
sys.path.insert(0, '/tmp/pair')
import numpy as np
import pandas as pd
from ladder_baseline_study import load_parquet_windows
from box_policy_ab import hedge_unpaired, tstat, maxdd, sortino


# ============================================================
# Per-window pairing walk (P0 always-pair) -> identify the open opening leg and per-fill strand mark
# A window strands if, after the natural net-walk, an opening leg is left unpaired.
# ============================================================

def p_yeq(f):
    return f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)


def micro_divergence(f):
    """Microprice / book-imbalance proxy from decision-time fields.
    We have YES-equiv price p, spread. The fill price p sits at one touch; |p - 0.5| measures how
    far the box midpoint is from the symmetric 0.5 (a skewed book -> harder to pair the other side).
    Also use flow as a directional pressure proxy (taker imbalance pushing price away from our
    resting other leg)."""
    return abs(p_yeq(f) - 0.5)


def both_side_depth(f):
    """min(depth) -- the harness gives top-5 displayed size (min of the two touch levels already in
    window_fills as 'depth'). NaN -> treat as 0 (unknown = thin)."""
    d = f.get('depth')
    if d is None or (isinstance(d, float) and np.isnan(d)):
        return 0.0
    return float(d)


# ============================================================
# WALK with a generic open-gate; compute window-level strand + box pnl + disposal accounting.
# disposal: 'hold' (settle), 'early' (exit at k+1 cross), 'hedge' (perp), 'capcross' (early cross
# unless the lock is worse than -give_cap, then hold).
# ============================================================

def walk_gate(fills_per_ws, ws_list, gate=None, disposal='hold', give_cap=None):
    """Returns dict with per-window pnl array, strand bool array, opened-count, paired-box count,
    and disposal cost array for stranded legs."""
    pnl_arr = []
    strand_arr = []
    opened_any = []        # window had at least one opening leg (i.e. we traded the window)
    box_pnls = []          # per paired-box pnl (settle_yes + settle_no), for paired-box edge
    disp_costs = []        # disposal cost per stranded leg
    n_open_legs = 0
    n_paired_legs = 0

    for ws in ws_list:
        fills = fills_per_ws[ws]
        net = 0
        pnl = 0.0
        open_leg = None
        opened = False
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                # pairing fill -- completes the box (pairing leg always fills in replay)
                box = f['settle'] + (open_leg['settle'] if open_leg else 0.0)
                pnl += box
                box_pnls.append(box)
                n_paired_legs += 1
                open_leg = None
            else:
                # opening leg -- apply the gate
                if gate is not None and not gate(f):
                    continue
                open_leg = f
                opened = True
                n_open_legs += 1
            net = nn

        stranded = open_leg is not None
        if stranded:
            dc = disposal_value(open_leg, disposal, give_cap)
            pnl += dc
            disp_costs.append(dc)

        pnl_arr.append(pnl)
        strand_arr.append(stranded)
        opened_any.append(opened)

    return dict(
        pnl=np.array(pnl_arr, float),
        strand=np.array(strand_arr, bool),
        opened=np.array(opened_any, bool),
        box_pnls=np.array(box_pnls, float),
        disp_costs=np.array(disp_costs, float),
        n_open_legs=n_open_legs,
        n_paired_legs=n_paired_legs,
    )


def disposal_value(f, mode, give_cap):
    """Value of an unpaired (stranded) leg under a disposal mode (in $/contract; negative = loss)."""
    hold = f['settle']
    early = f.get('exit', hold)   # sell-back ~1 min later at the touch (cheap early cross)
    if mode == 'hold':
        return hold
    if mode == 'early':
        return early
    if mode == 'hedge':
        return hedge_unpaired(f, h=150.0)
    if mode == 'capcross':
        # Cross early UNLESS the lock-in loss is worse than -give_cap, then HOLD (bounded).
        # give_cap in $ (e.g. 0.22 = accept up to -22c lock). If early cross locks worse, hold.
        if early < -abs(give_cap):
            return hold
        return early
    return hold


# ============================================================
# STRAND-RATE BY ENTRY CONDITION
# Label each OPENING fill with whether its window ended stranded (under no-gate P0 walk).
# ============================================================

def opening_fill_table(fills_per_ws, ws_list):
    """Return DataFrame: one row per OPENING fill, with entry conditions + window stranded flag."""
    rows = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        net = 0
        open_leg = None
        opening_fills = []
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                open_leg = None
            else:
                open_leg = f
                opening_fills.append(f)
            net = nn
        win_stranded = open_leg is not None
        # The marginal opening leg (the last open_leg) is the one that strands; but for gating we
        # care about the entry conditions of EACH opening leg, attributing the window strand outcome.
        # Standard approach: label the opening leg(s) by whether THIS leg ends stranded.
        # Identify the stranded leg precisely:
        stranded_leg = open_leg
        for f in opening_fills:
            rows.append(dict(
                ws=ws,
                side=f['side'],
                p_yeq=p_yeq(f),
                divergence=micro_divergence(f),
                depth=both_side_depth(f),
                spread=f.get('spread', np.nan),
                k=f.get('k', np.nan),
                absig=abs(f.get('sig', 0.0) or 0.0),
                absflow=abs(f.get('flow', 0.0) or 0.0),
                vpin=f.get('vpin') if f.get('vpin') is not None else np.nan,
                this_leg_strand=1 if (f is stranded_leg) else 0,
                exit=f.get('exit', np.nan),
                settle=f.get('settle', np.nan),
            ))
    return pd.DataFrame(rows)


def bucket_table(df, col, bins, labels):
    df = df.copy()
    df['bucket'] = pd.cut(df[col], bins=bins, labels=labels, include_lowest=True)
    g = df.groupby('bucket', observed=True)['this_leg_strand'].agg(['mean', 'count'])
    g['strand_pct'] = g['mean'] * 100
    return g[['strand_pct', 'count']]


def main():
    out = []
    def pr(s=''):
        print(s)
        out.append(s)

    pr("=" * 70)
    pr("PAIR-GATE STUDY (BTC 15m maker-box)")
    pr("=" * 70)

    fills_btc, ws_btc = load_parquet_windows('btc')
    n = len(ws_btc)
    cut = int(n * 0.6)
    ws_is, ws_oos = ws_btc[:cut], ws_btc[cut:]
    pr(f"BTC windows with fills: {n}  IS={len(ws_is)} OOS={len(ws_oos)}")

    # ---- Baseline (no gate) ----
    base = walk_gate(fills_btc, ws_btc, gate=None, disposal='hold')
    base_is = walk_gate(fills_btc, ws_is, gate=None, disposal='hold')
    base_oos = walk_gate(fills_btc, ws_oos, gate=None, disposal='hold')
    traded_base = base['opened'].sum()
    pr(f"\n[BASELINE no-gate, hold disposal]")
    pr(f"  windows traded (opened a leg): {traded_base}/{n} = {traded_base/n*100:.1f}%")
    pr(f"  strand rate (of traded windows): {base['strand'].sum()/max(traded_base,1)*100:.1f}%")
    pr(f"  paired boxes: {len(base['box_pnls'])}  mean box edge = {base['box_pnls'].mean()*100:+.3f}c")
    pr(f"  net/window = {base['pnl'].mean()*100:+.3f}c   net/traded-window = {base['pnl'][base['opened']].mean()*100:+.3f}c")
    pr(f"  OOS strand={base_oos['strand'].sum()/max(base_oos['opened'].sum(),1)*100:.1f}%  net/win={base_oos['pnl'][base_oos['opened']].mean()*100:+.3f}c")

    # ---- STRAND-RATE BY ENTRY CONDITION ----
    df = opening_fill_table(fills_btc, ws_btc)
    df_is = opening_fill_table(fills_btc, ws_is)
    pr(f"\n[OPENING FILLS]: {len(df)} opening legs, overall per-leg strand rate = {df['this_leg_strand'].mean()*100:.1f}%")

    pr("\n=== STRAND RATE BY ENTRY CONDITION (per opening leg) ===")

    pr("\n(a) MICROPRICE DIVERGENCE |p_yeq - 0.5| (book skew):")
    bt = bucket_table(df, 'divergence', [0, 0.05, 0.10, 0.15, 0.20, 0.5],
                      ['0-.05', '.05-.10', '.10-.15', '.15-.20', '.20+'])
    for idx, r in bt.iterrows():
        pr(f"   {idx:>10}: strand={r['strand_pct']:5.1f}%  n={int(r['count'])}")

    pr("\n(b) MIN BOTH-SIDE DEPTH (top-5 displayed):")
    qs = df['depth'].quantile([0, .2, .4, .6, .8, 1.0]).values
    qs = sorted(set(np.round(qs, 1)))
    bt = bucket_table(df, 'depth', qs if len(qs) > 2 else [0, 50, 100, 200, 1e9],
                      None if len(qs) > 2 else None)
    # build labels
    df2 = df.copy()
    try:
        df2['bucket'] = pd.qcut(df2['depth'], 5, duplicates='drop')
        g = df2.groupby('bucket', observed=True)['this_leg_strand'].agg(['mean', 'count'])
        for idx, r in g.iterrows():
            pr(f"   {str(idx):>22}: strand={r['mean']*100:5.1f}%  n={int(r['count'])}")
    except Exception as e:
        pr(f"   depth bucketing failed: {e}")

    pr("\n(c) SPREAD:")
    df2 = df.copy()
    df2['bucket'] = pd.cut(df2['spread'], [0, 0.01, 0.02, 0.03, 1.0],
                           labels=['<=1c', '2c', '3c', '4c+'], include_lowest=True)
    g = df2.groupby('bucket', observed=True)['this_leg_strand'].agg(['mean', 'count'])
    for idx, r in g.iterrows():
        pr(f"   {str(idx):>8}: strand={r['mean']*100:5.1f}%  n={int(r['count'])}")

    pr("\n(d) K-SLOT (minute):")
    g = df.groupby('k', observed=True)['this_leg_strand'].agg(['mean', 'count'])
    for idx, r in g.iterrows():
        pr(f"   k={int(idx):>2}: strand={r['mean']*100:5.1f}%  n={int(r['count'])}")

    pr("\n(e) |SIG| (spot bps move):")
    df2 = df.copy()
    df2['bucket'] = pd.cut(df2['absig'], [0, 2, 5, 10, 20, 1e9],
                           labels=['0-2', '2-5', '5-10', '10-20', '20+'], include_lowest=True)
    g = df2.groupby('bucket', observed=True)['this_leg_strand'].agg(['mean', 'count'])
    for idx, r in g.iterrows():
        pr(f"   {str(idx):>8}: strand={r['mean']*100:5.1f}%  n={int(r['count'])}")

    pr("\n(f) |FLOW| (taker imbalance):")
    df2 = df.copy()
    try:
        df2['bucket'] = pd.qcut(df2['absflow'], 5, duplicates='drop')
        g = df2.groupby('bucket', observed=True)['this_leg_strand'].agg(['mean', 'count'])
        for idx, r in g.iterrows():
            pr(f"   {str(idx):>22}: strand={r['mean']*100:5.1f}%  n={int(r['count'])}")
    except Exception as e:
        pr(f"   flow bucketing failed: {e}")

    # ---- depth distribution to pick thresholds ----
    pr(f"\nDEPTH distribution: min={df['depth'].min():.0f} "
       f"q25={df['depth'].quantile(.25):.0f} med={df['depth'].median():.0f} "
       f"q75={df['depth'].quantile(.75):.0f} max={df['depth'].max():.0f} "
       f"frac_zero={ (df['depth']==0).mean()*100:.1f}%")
    pr(f"DIVERGENCE dist: med={df['divergence'].median():.3f} q75={df['divergence'].quantile(.75):.3f} q90={df['divergence'].quantile(.9):.3f}")

    # ============================================================
    # GATE SEARCH: grid over (max_divergence, min_depth, spread, k) -> strand rate + volume + net
    # ============================================================
    pr("\n=== GATE GRID SEARCH (target: strand<5%, keep volume) ===")
    pr(f"{'gate':<48} {'traded%':>8} {'strand%':>8} {'boxedge':>8} {'net/win':>9} {'net/box':>8}")
    pr("-" * 95)

    def make_gate(max_div=1.0, min_depth=0.0, min_spread=0.0, max_spread=1.0,
                  kmin=2, kmax=12, max_absig=1e9, max_absflow=1e9):
        def g(f):
            if micro_divergence(f) > max_div: return False
            if both_side_depth(f) < min_depth: return False
            sp = f.get('spread', 0.0)
            if sp < min_spread or sp > max_spread: return False
            kk = f.get('k', 7)
            if kk < kmin or kk > kmax: return False
            if abs(f.get('sig', 0.0) or 0.0) > max_absig: return False
            if abs(f.get('flow', 0.0) or 0.0) > max_absflow: return False
            return True
        return g

    candidates = {
        "no-gate": dict(),
        "div<=.10": dict(max_div=0.10),
        "div<=.05": dict(max_div=0.05),
        "depth>=med": dict(min_depth=df['depth'].median()),
        "depth>=q75": dict(min_depth=df['depth'].quantile(.75)),
        "div<=.10+depth>=med": dict(max_div=0.10, min_depth=df['depth'].median()),
        "div<=.05+depth>=q75": dict(max_div=0.05, min_depth=df['depth'].quantile(.75)),
        "div<=.10+depth>=med+sp>=2c": dict(max_div=0.10, min_depth=df['depth'].median(), min_spread=0.02),
        "div<=.05+depth>=med+|sig|<10": dict(max_div=0.05, min_depth=df['depth'].median(), max_absig=10),
        "div<=.05+depth>=q75+|sig|<10": dict(max_div=0.05, min_depth=df['depth'].quantile(.75), max_absig=10),
        "div<=.05+depth>=q75+k>=4": dict(max_div=0.05, min_depth=df['depth'].quantile(.75), kmin=4),
        "div<=.03+depth>=q75": dict(max_div=0.03, min_depth=df['depth'].quantile(.75)),
        "div<=.05+depth>=q75+|sig|<5+|flow|<med": dict(
            max_div=0.05, min_depth=df['depth'].quantile(.75), max_absig=5,
            max_absflow=df['absflow'].median()),
        # k-capped families: catastrophic strands cluster at k=11-12 (last 1-3 min); cap k.
        "k<=10": dict(kmax=10),
        "k<=9": dict(kmax=9),
        "depth>=med+k<=10": dict(min_depth=df['depth'].median(), kmax=10),
        "depth>=med+k<=9": dict(min_depth=df['depth'].median(), kmax=9),
        "depth>=q75+k<=10": dict(min_depth=df['depth'].quantile(.75), kmax=10),
        "div<=.10+depth>=med+k<=10": dict(max_div=0.10, min_depth=df['depth'].median(), kmax=10),
        "div<=.10+depth>=med+k<=9": dict(max_div=0.10, min_depth=df['depth'].median(), kmax=9),
        "depth>=med+k<=10+|sig|<10": dict(min_depth=df['depth'].median(), kmax=10, max_absig=10),
        "depth>=med+k<=9+|sig|<10": dict(min_depth=df['depth'].median(), kmax=9, max_absig=10),
    }

    results = {}
    for name, kw in candidates.items():
        g = make_gate(**kw) if kw else None
        r = walk_gate(fills_btc, ws_btc, gate=g, disposal='hold')
        traded = r['opened'].sum()
        strand_rate = r['strand'].sum() / max(traded, 1) * 100
        boxedge = r['box_pnls'].mean() * 100 if len(r['box_pnls']) else float('nan')
        netwin = r['pnl'][r['opened']].mean() * 100 if traded else float('nan')
        # net/box: total pnl / number of boxes (paired)
        nbox = len(r['box_pnls'])
        netbox = r['pnl'].sum() / nbox * 100 if nbox else float('nan')
        results[name] = (traded/n*100, strand_rate, boxedge, netwin, netbox, nbox, kw)
        pr(f"{name:<48} {traded/n*100:7.1f}% {strand_rate:7.1f}% {boxedge:+7.3f}c {netwin:+8.3f}c {netbox:+7.3f}c")

    # ============================================================
    # DISPOSAL COST BY TIMING (on the residual strands of the no-gate baseline, and of best gate)
    # ============================================================
    pr("\n=== DISPOSAL COST BY TIMING (residual stranded legs) ===")
    strand_legs = df[df['this_leg_strand'] == 1].copy()
    pr(f"Stranded legs: n={len(strand_legs)}")
    pr(f"  HOLD (settle to expiry):    mean={strand_legs['settle'].mean()*100:+.2f}c  "
       f"p10={strand_legs['settle'].quantile(.1)*100:+.1f}c  p90={strand_legs['settle'].quantile(.9)*100:+.1f}c")
    pr(f"  EARLY cross (exit at k+1):  mean={strand_legs['exit'].mean()*100:+.2f}c  "
       f"p10={strand_legs['exit'].quantile(.1)*100:+.1f}c  p90={strand_legs['exit'].quantile(.9)*100:+.1f}c")
    worst_hold = strand_legs['settle'].min() * 100
    worst_early = strand_legs['exit'].min() * 100
    pr(f"  worst HOLD lock = {worst_hold:+.1f}c ; worst EARLY lock = {worst_early:+.1f}c")

    pr("\n  GIVE-CAP sweep (cross early unless lock worse than -cap, then hold):")
    pr(f"  {'cap':>6} {'mean_disp':>10} {'worst':>8} {'%held':>7}")
    for cap in [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.22, 0.30, 1.0]:
        vals = []
        held = 0
        for _, r in strand_legs.iterrows():
            early = r['exit']
            if early < -cap:
                vals.append(r['settle']); held += 1
            else:
                vals.append(early)
        vals = np.array(vals)
        pr(f"  {cap*100:5.0f}c {vals.mean()*100:+9.2f}c {vals.min()*100:+7.1f}c {held/len(vals)*100:6.1f}%")

    # ============================================================
    # COMBINED: best gate + best disposal, IS/OOS stability + Sharpe
    # ============================================================
    pr("\n=== COMBINED (pair-gate + capped early disposal), IS vs OOS ===")
    # pick best gate: strand<5% AND traded>=15% (meaningful volume), maximize net/box (v[4])
    viable = {k: v for k, v in results.items()
              if v[1] < 5.0 and v[0] >= 15.0 and k != 'no-gate' and np.isfinite(v[4])}
    if viable:
        best = max(viable.items(), key=lambda kv: kv[1][4])  # max net/box among strand<5%, vol>=15%
        best_name, best_v = best
    else:
        # fall back to lowest strand with any volume
        best = min(((k, v) for k, v in results.items() if k != 'no-gate'),
                   key=lambda kv: kv[1][1])
        best_name, best_v = best
    pr(f"(viable gates strand<5% & traded>=15%: {sorted(viable, key=lambda k: -viable[k][4])})")
    pr(f"Selected gate: {best_name}  (strand={best_v[1]:.1f}%, traded={best_v[0]:.1f}%)")
    best_kw = best_v[6]

    # determine best give-cap: smallest cap whose worst-case is bounded but mean best
    # recompute disp sweep to pick optimal
    def disp_mean(cap):
        vals = []
        for _, r in strand_legs.iterrows():
            early = r['exit']
            vals.append(r['settle'] if early < -cap else early)
        return np.mean(vals)
    cap_grid = [0.08, 0.10, 0.12, 0.15, 0.18, 0.22]
    best_cap = max(cap_grid, key=lambda c: disp_mean(c)) if len(strand_legs) else 0.12
    pr(f"Selected give-cap: {best_cap*100:.0f}c (early-cross unless lock worse, else hold)")

    g = make_gate(**best_kw)
    for label, wl, baseref in [("IS", ws_is, base_is), ("OOS", ws_oos, base_oos)]:
        r = walk_gate(fills_btc, wl, gate=g, disposal='capcross', give_cap=best_cap)
        traded = r['opened'].sum()
        nw = len(wl)
        strand_rate = r['strand'].sum() / max(traded, 1) * 100
        nbox = len(r['box_pnls'])
        netbox = r['pnl'].sum() / nbox * 100 if nbox else float('nan')
        # Sharpe over traded windows
        px = r['pnl'][r['opened']]
        sh = px.mean() / px.std(ddof=1) if len(px) > 3 and px.std() > 0 else float('nan')
        boxedge = r['box_pnls'].mean()*100 if nbox else float('nan')
        pr(f"  [{label}] traded={traded}/{nw}={traded/nw*100:.1f}%  strand={strand_rate:.1f}%  "
           f"boxedge={boxedge:+.3f}c  net/box={netbox:+.3f}c  net/win={px.mean()*100:+.3f}c  Sharpe={sh:+.3f}")

    # also report the gate+disposal on full set
    r = walk_gate(fills_btc, ws_btc, gate=g, disposal='capcross', give_cap=best_cap)
    nbox = len(r['box_pnls']); traded = r['opened'].sum()
    pr(f"\n  [FULL] traded={traded/n*100:.1f}%  strand={r['strand'].sum()/max(traded,1)*100:.1f}%  "
       f"net/box={r['pnl'].sum()/nbox*100:+.3f}c  net/win={r['pnl'][r['opened']].mean()*100:+.3f}c")

    # ---- ETH cross-check ----
    pr("\n=== ETH cross-check (same gate+disposal) ===")
    try:
        fills_eth, ws_eth = load_parquet_windows('eth')
        dfe = opening_fill_table(fills_eth, ws_eth)
        # use BTC-derived thresholds
        ge = make_gate(**best_kw)
        re = walk_gate(fills_eth, ws_eth, gate=ge, disposal='capcross', give_cap=best_cap)
        rb = walk_gate(fills_eth, ws_eth, gate=None, disposal='hold')
        tre = re['opened'].sum(); ne = len(ws_eth); nbe = len(re['box_pnls'])
        pr(f"  ETH no-gate: traded={rb['opened'].sum()/ne*100:.1f}% strand={rb['strand'].sum()/max(rb['opened'].sum(),1)*100:.1f}% net/box={rb['pnl'].sum()/max(len(rb['box_pnls']),1)*100:+.3f}c")
        pr(f"  ETH gated:   traded={tre/ne*100:.1f}% strand={re['strand'].sum()/max(tre,1)*100:.1f}% net/box={re['pnl'].sum()/max(nbe,1)*100:+.3f}c")
    except Exception as e:
        pr(f"  ETH check failed: {e}")

    # save the chosen params for the report
    global CHOSEN
    CHOSEN = dict(name=best_name, kw=best_kw, cap=best_cap, results=results,
                  strand_legs=strand_legs, base=base, df=df, n=n,
                  fills_btc=fills_btc, ws_is=ws_is, ws_oos=ws_oos, ws_btc=ws_btc,
                  make_gate=make_gate, walk_gate=walk_gate)

    with open('/tmp/pair/_pair_gate_output.txt', 'w') as fh:
        fh.write("\n".join(out))
    return out


if __name__ == '__main__':
    main()
