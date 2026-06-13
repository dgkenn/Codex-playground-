"""box_yield_edge.py -- Box-yield EDGE study (GAIN side of the 15m crypto box bot).

FOCUS: the SECOND term of TOTAL PnL = (#boxes) x (avg locked edge/box) - strand losses.
  -> WHEN are boxes fattest (widest lock margin), and how to SIZE capital onto fat boxes.
  -> Does adding ETH (+ by extension SOL/XRP) give profitable diversifying breadth?

Tasks:
  1. Baseline avg lock-margin/box + total locked-edge under live policy.
  2. Edge-by-regime tables: k-slot, UTC session, vol-regime (|sig|). NET edge = margin - E[strand cost].
  3. Edge-proportional sizing: fractional-Kelly on the locked margin net of strand prob. Sweep f.
  4. Cross-asset breadth: BTC vs ETH yield, portfolio Sharpe BTC+ETH vs BTC alone.
  5. Avellaneda-Stoikov reservation-price note; honest noise calls; IS/OOS stability.

Reuses load_parquet_windows / run_p0 / full_metrics from ladder_baseline_study.
Writes nothing; main() prints the tables that get pasted into BOXYIELD_EDGE.md.
"""
from __future__ import annotations
import sys, datetime as dt
sys.path.insert(0, '/tmp/by_edge')
import numpy as np

from ladder_baseline_study import load_parquet_windows, run_p0, full_metrics
from box_policy_ab import _live_open_ok, tstat, maxdd, sortino, hedge_unpaired


# ============================================================
# BOX RECONSTRUCTION (per-window walk -> list of boxes + strands)
# ============================================================
# A BOX = one YES(bid) leg + one NO(ask) leg paired in the window.
# Locked margin of the box = sum of the two legs' settle = (res-b0)+(a0-res) = a0 - b0
#   i.e. the spread captured between the NO-leg entry (a0) and the YES-leg entry (b0).
# This is RES-INDEPENDENT => a completed box is near-risk-free; its PnL is the captured spread.
# A STRAND = an open leg that never paired; its PnL is res-dependent (the directional risk).

def walk_boxes(fills, open_ok=None):
    """Return (boxes, strand). boxes=list of dicts {margin, k_open, k_pair, sig, ...};
    strand = the leftover open-leg dict (or None). open_ok gates OPENING legs (live policy)."""
    net = 0; open_leg = None; boxes = []
    for f in fills:
        step = 1 if f['side'] == 'bid' else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        pairing = (net != 0 and abs(nn) < abs(net))
        if pairing:
            # margin = the two legs' summed settle = captured spread (res cancels)
            margin = f['settle'] + open_leg['settle']
            boxes.append({
                'margin': margin,
                'k_open': open_leg['k'], 'k_pair': f['k'],
                'sig_open': open_leg.get('sig', 0.0) or 0.0,
                'spread_open': open_leg.get('spread', 0.0),
                'spread_pair': f.get('spread', 0.0),
                'side_open': open_leg['side'],
            })
            open_leg = None
            net = nn
            continue
        # opening fill
        if open_ok is not None and not open_ok(f, {}):
            continue
        open_leg = f
        net = nn
    return boxes, open_leg


def window_features(fills):
    """Window-level features: mean |sig| (vol regime), n fills."""
    sigs = [abs(f.get('sig', 0.0) or 0.0) for f in fills]
    return {'mean_abs_sig': float(np.mean(sigs)) if sigs else 0.0, 'n_fills': len(fills)}


def utc_hour(ws):
    return dt.datetime.utcfromtimestamp(int(ws)).hour


def session_of(hour):
    # UTC session buckets
    if 0 <= hour < 7:   return 'Asia(00-07)'
    if 7 <= hour < 13:  return 'EU(07-13)'
    if 13 <= hour < 21: return 'US(13-21)'
    return 'LateUS(21-24)'


# ============================================================
# STRAND COST: expected $ loss/contract when a box fails to pair.
# Under live policy the strand is held to settle (R5 hedge demoted in lockdown);
# use realized strand settle as the empirical expected strand cost.
# ============================================================

def collect_box_records(fills_per_ws, ws_list, open_ok):
    """Per-window: boxes (each with margin + regime tags) and strand outcome.
    Returns list of per-box records and list of per-window strand records."""
    box_recs = []; strand_recs = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        wf = window_features(fills)
        hr = utc_hour(ws); sess = session_of(hr)
        boxes, strand = walk_boxes(fills, open_ok=open_ok)
        for b in boxes:
            b = dict(b)
            b['ws'] = ws; b['hour'] = hr; b['session'] = sess
            b['win_abs_sig'] = wf['mean_abs_sig']
            box_recs.append(b)
        if strand is not None:
            strand_recs.append({
                'ws': ws, 'hour': hr, 'session': sess,
                'settle': strand['settle'], 'k': strand['k'],
                'sig': abs(strand.get('sig', 0.0) or 0.0),
                'win_abs_sig': wf['mean_abs_sig'],
            })
    return box_recs, strand_recs


# ============================================================
# REGIME TABLES
# ============================================================

def regime_table(box_recs, strand_recs, key_fn, order=None, label='regime'):
    """avg lock-margin per box, n boxes, box-rate share, and NET edge per box
    = avg_margin - (strand_rate_in_regime * E[strand_cost_in_regime]) attributed per box.
    We attribute strand cost across boxes in the same regime (cost per opened box)."""
    from collections import defaultdict
    bx = defaultdict(list); st = defaultdict(list)
    for b in box_recs:
        bx[key_fn(b)].append(b['margin'])
    for s in strand_recs:
        st[key_fn(s)].append(s['settle'])
    keys = order if order else sorted(set(list(bx) + list(st)))
    rows = []
    for k in keys:
        m = np.array(bx.get(k, []), float)
        sc = np.array(st.get(k, []), float)   # strand settles (negative = loss)
        nbox = len(m); nstr = len(sc)
        avg_margin = m.mean()*100 if nbox else float('nan')
        # expected strand cost spread across boxes opened in this regime
        # total strand pnl / (#boxes + #strands) gives net drag per opened position
        n_open = nbox + nstr
        strand_drag = (sc.sum()/n_open*100) if n_open else 0.0
        net_edge = (m.sum()/n_open*100) + strand_drag if n_open else float('nan')
        strand_rate = nstr/n_open*100 if n_open else float('nan')
        rows.append((k, nbox, avg_margin, nstr, strand_rate, net_edge,
                     tstat(m) if nbox >= 8 else float('nan')))
    return rows


def print_regime(title, rows, keyhdr='regime'):
    print(f"\n### {title}")
    print(f"{keyhdr:<16} {'nBox':>6} {'avgMargin':>10} {'nStr':>5} {'Str%':>6} {'NETedge':>8} {'t(margin)':>9}")
    print('-'*70)
    for k, nbox, am, nstr, sr, ne, t in rows:
        print(f"{str(k):<16} {nbox:>6} {am:>+9.3f}c {nstr:>5} {sr:>5.1f}% {ne:>+7.3f}c {t:>+8.2f}")


# ============================================================
# SIZING: flat vs edge-proportional (fractional-Kelly on locked margin net of strand prob)
# ============================================================
# A completed box is ~risk-free => the "edge" is the locked margin m (cents).
# The risk is the strand: with prob q the position strands and loses ~L.
# Fractional-Kelly-style size ~ f * (expected net edge), clipped. We size each OPENED
# position by the predicted margin of its regime, normalized so mean size = 1 (capital-neutral
# comparison of allocation, not leverage). Then PnL_window = sum(size_i * leg_settle_i).

def size_walk(fills_per_ws, ws_list, open_ok, size_fn):
    """Walk windows applying per-opening-leg size = size_fn(open_leg, window_feats).
    Both legs of a box inherit the OPENING leg's size (the box is sized at entry)."""
    pnl_arr = []; strand_arr = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        wf = window_features(fills)
        hr = utc_hour(ws)
        net = 0; open_leg = None; open_sz = 1.0; pnl = 0.0; stranded = False
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            pairing = (net != 0 and abs(nn) < abs(net))
            if pairing:
                pnl += open_sz * (f['settle'] + open_leg['settle'])
                open_leg = None; open_sz = 1.0; net = nn
                continue
            if open_ok is not None and not open_ok(f, {}):
                continue
            open_sz = size_fn(f, wf, hr)
            open_leg = f; net = nn
        if open_leg is not None:
            stranded = True
            pnl += open_sz * open_leg['settle']   # strand held to settle (R5 demoted)
        pnl_arr.append(pnl); strand_arr.append(stranded)
    return np.array(pnl_arr, float), np.array(strand_arr, bool)


def build_regime_edge_map(box_recs, strand_recs):
    """Map (session, vol-bucket) -> net edge per opened position (cents), estimated IS.
    Used as the predicted edge for edge-proportional sizing (no per-fill leakage of outcome)."""
    from collections import defaultdict
    def vbucket(s):
        if s < 3: return 'lo'
        if s < 8: return 'mid'
        return 'hi'
    agg = defaultdict(lambda: [0.0, 0])  # [sum_pnl, n_open]
    for b in box_recs:
        key = (b['session'], vbucket(b['win_abs_sig']))
        agg[key][0] += b['margin']; agg[key][1] += 1
    for s in strand_recs:
        key = (s['session'], vbucket(s['win_abs_sig']))
        agg[key][0] += s['settle']; agg[key][1] += 1
    emap = {}
    for k, (sp, n) in agg.items():
        emap[k] = sp/n if n else 0.0
    return emap, vbucket


# ============================================================
# CROSS-ASSET PORTFOLIO
# ============================================================

def align_portfolio(pnl_a_by_ws, pnl_b_by_ws):
    """Align two per-ws PnL dicts on common windows; return (a, b, combo50/50)."""
    common = sorted(set(pnl_a_by_ws) & set(pnl_b_by_ws))
    a = np.array([pnl_a_by_ws[w] for w in common])
    b = np.array([pnl_b_by_ws[w] for w in common])
    return a, b, 0.5*(a+b), common


def pnl_by_ws(fills_per_ws, ws_list, open_ok):
    d = {}
    for ws in ws_list:
        boxes, strand = walk_boxes(fills_per_ws[ws], open_ok=open_ok)
        pnl = sum(b['margin'] for b in boxes)
        if strand is not None:
            pnl += strand['settle']
        d[ws] = pnl
    return d


def sharpe(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    s = x.std(ddof=1)
    return x.mean()/s if s > 1e-12 else float('nan')


# ============================================================
# MAIN
# ============================================================

def split(ws_list):
    cut = int(len(ws_list)*0.6)
    return ws_list[:cut], ws_list[cut:]


def main():
    print("="*78)
    print("BOX-YIELD EDGE STUDY")
    print("="*78)
    LIVE = _live_open_ok

    print("\nLoading BTC...")
    fb, wb = load_parquet_windows('btc')
    print("Loading ETH...")
    fe, we = load_parquet_windows('eth')
    wb_is, wb_oos = split(wb)
    we_is, we_oos = split(we)

    # ---------- TASK 1: BASELINE ----------
    print("\n" + "="*78); print("TASK 1: BASELINE LOCK-MARGIN (live policy = t36 guarded-opener)")
    print("="*78)
    for name, fp, wsl in [('BTC IS', fb, wb_is), ('BTC OOS', fb, wb_oos),
                          ('BTC ALL', fb, wb)]:
        box, strand = collect_box_records(fp, wsl, LIVE)
        m = np.array([b['margin'] for b in box])
        scost = np.array([s['settle'] for s in strand])
        nwin = len(wsl)
        tot_locked = m.sum()*100
        tot_strand = scost.sum()*100
        print(f"\n{name}: windows={nwin}  boxes={len(m)}  strands={len(strand)}")
        print(f"  avg lock-margin/box = {m.mean()*100:+.3f}c  (t={tstat(m):+.2f}, median={np.median(m)*100:+.2f}c)")
        print(f"  total locked-edge   = {tot_locked:+.1f}c  over {len(m)} boxes")
        print(f"  total strand pnl    = {tot_strand:+.1f}c  over {len(strand)} strands "
              f"(avg {scost.mean()*100 if len(scost) else 0:+.2f}c)")
        print(f"  NET total           = {tot_locked+tot_strand:+.1f}c  "
              f"({(tot_locked+tot_strand)/nwin:+.3f}c/window)")
        print(f"  box fill-rate       = {len(m)/nwin:.3f} boxes/window  strand-rate={len(strand)/nwin*100:.1f}%/win")

    # also vs P0 (no gate) for reference
    p0o, p0o_st = run_p0(fb, wb_oos)
    print(f"\n  [ref] BTC OOS P0 (no gate): net={p0o.mean()*100:+.3f}c/win  strand={p0o_st.mean()*100:.1f}%")

    # ---------- TASK 2: EDGE BY REGIME ----------
    print("\n" + "="*78); print("TASK 2: EDGE BY REGIME (BTC, live policy)")
    print("="*78)
    box_all, strand_all = collect_box_records(fb, wb, LIVE)
    box_oos, strand_oos = collect_box_records(fb, wb_oos, LIVE)

    # by k-slot (opening minute)
    rows = regime_table(box_all, strand_all, lambda r: r.get('k_open', r.get('k')),
                        order=list(range(2,13)))
    print_regime("Edge by k-slot (opening minute 2-12) [ALL]", rows, 'k_open')

    # by session
    rows = regime_table(box_all, strand_all, lambda r: r['session'],
                        order=['Asia(00-07)','EU(07-13)','US(13-21)','LateUS(21-24)'])
    print_regime("Edge by UTC session [ALL]", rows, 'session')

    # by vol regime (window mean |sig|)
    def volb(r):
        s = r['win_abs_sig']
        return 'lo(<3)' if s < 3 else ('mid(3-8)' if s < 8 else 'hi(>=8)')
    rows = regime_table(box_all, strand_all, volb, order=['lo(<3)','mid(3-8)','hi(>=8)'])
    print_regime("Edge by vol-regime (window mean|sig| bps) [ALL]", rows, 'vol')

    # OOS stability of vol regime
    rows = regime_table(box_oos, strand_oos, volb, order=['lo(<3)','mid(3-8)','hi(>=8)'])
    print_regime("Edge by vol-regime [OOS only -- stability check]", rows, 'vol')

    # ---------- TASK 3: EDGE-PROPORTIONAL SIZING ----------
    print("\n" + "="*78); print("TASK 3: EDGE-PROPORTIONAL SIZING (fractional-Kelly on locked margin)")
    print("="*78)
    # Build IS regime edge map; size OOS by it (no leakage: map from IS only)
    box_is, strand_is = collect_box_records(fb, wb_is, LIVE)
    emap, vbucket = build_regime_edge_map(box_is, strand_is)
    mean_edge = np.mean([v for v in emap.values()]) or 1e-6

    def make_size_fn(frac):
        def sz(f, wf, hr):
            key = (session_of(hr), vbucket(wf['mean_abs_sig']))
            e = emap.get(key, mean_edge)
            # fractional-Kelly: size proportional to edge, scaled by frac, floored at 0
            raw = 1.0 + frac * (e - mean_edge) / (abs(mean_edge) + 1e-6)
            return max(0.0, min(raw, 3.0))
        return sz

    # flat baseline OOS
    flat, flat_st = size_walk(fb, wb_oos, LIVE, lambda f,wf,hr: 1.0)
    mf = full_metrics(flat, flat, flat)
    print(f"\n{'Policy':<22} {'net/win':>9} {'Sharpe':>8} {'Sortino':>8} {'MaxDD':>8} {'WR%':>6} {'t':>7}")
    print('-'*72)
    print(f"{'flat size (live)':<22} {mf['nc']:>+8.3f}c {mf['sh']:>+8.3f} {mf['sor']:>+8.3f} "
          f"{mf['mdd']:>7.2f}c {mf['wr']:>5.1f}% {mf['ts']:>+6.2f}")
    best = (None, -1e9)
    for frac in [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]:
        es, est = size_walk(fb, wb_oos, LIVE, make_size_fn(frac))
        me = full_metrics(es, flat, flat)
        # paired-difference t-stat edge-size vs flat
        d = es - flat; dt_ = tstat(d)
        print(f"{'edge-size f='+str(frac):<22} {me['nc']:>+8.3f}c {me['sh']:>+8.3f} {me['sor']:>+8.3f} "
              f"{me['mdd']:>7.2f}c {me['wr']:>5.1f}% {me['ts']:>+6.2f}  dVsFlat={d.mean()*100:+.3f}c (td={dt_:+.2f})")
        if me['sh'] > best[1]:
            best = (frac, me['sh'])
    print(f"\n  best-Sharpe edge fraction (OOS): f={best[0]} (Sharpe={best[1]:+.3f} vs flat {mf['sh']:+.3f})")

    # ---------- TASK 4: CROSS-ASSET BREADTH ----------
    print("\n" + "="*78); print("TASK 4: CROSS-ASSET BREADTH (BTC vs ETH)")
    print("="*78)
    for name, fp, wsl in [('BTC OOS', fb, wb_oos), ('ETH OOS', fe, we_oos)]:
        box, strand = collect_box_records(fp, wsl, LIVE)
        m = np.array([b['margin'] for b in box])
        pser = pnl_by_ws(fp, wsl, LIVE)
        ps = np.array(list(pser.values()))
        print(f"\n{name}: boxes/win={len(m)/len(wsl):.3f}  avgMargin={m.mean()*100:+.3f}c  "
              f"strand-rate={len(strand)/len(wsl)*100:.1f}%  net/win={ps.mean()*100:+.3f}c  Sharpe={sharpe(ps):+.3f}")

    # Portfolio: align BTC & ETH on common ws (OOS)
    pb = pnl_by_ws(fb, wb_oos, LIVE)
    pe = pnl_by_ws(fe, we_oos, LIVE)
    a, b, combo, common = align_portfolio(pb, pe)
    corr = np.corrcoef(a, b)[0,1] if len(a) > 2 else float('nan')
    print(f"\nPortfolio (common OOS windows={len(common)}):")
    print(f"  BTC alone:  net/win={a.mean()*100:+.3f}c  Sharpe={sharpe(a):+.3f}")
    print(f"  ETH alone:  net/win={b.mean()*100:+.3f}c  Sharpe={sharpe(b):+.3f}")
    print(f"  50/50 BTC+ETH: net/win={combo.mean()*100:+.3f}c  Sharpe={sharpe(combo):+.3f}")
    print(f"  BTC-ETH window-PnL correlation = {corr:+.3f}")
    # diversification: sum (full capital each) -> total throughput
    summ = a + b
    print(f"  SUM (both books full size): net/win={summ.mean()*100:+.3f}c  Sharpe={sharpe(summ):+.3f}  "
          f"(2x boxes/win throughput)")
    # t-stat of combo Sharpe improvement is hard; report paired diff of combo vs BTC
    dcombo = combo - a
    print(f"  50/50 vs BTC-alone paired diff: {dcombo.mean()*100:+.3f}c/win (t={tstat(dcombo):+.2f})")

    print("\nDone. Tables above -> BOXYIELD_EDGE.md")


if __name__ == '__main__':
    main()
