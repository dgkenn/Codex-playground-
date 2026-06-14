"""edge_optimize_study.py -- Push the validated pair-gate maker-box edge higher.

Reuses pair_gate_study.walk_gate / make_gate / opening_fill_table (the VALIDATED harness).
Validated baseline config:
    gate = depth>=33000 + k<=10 + |sig|<10 ; disposal = capcross give-cap 15c
    => strand 1.9%, net/box +0.46c, IS==OOS, keeps 86% volume.

Sweeps (BTC primary; ETH/SOL/XRP cross-checks):
  1. DEPTH threshold {15k,25k,33k,50k,75k}
  2. GIVE-CAP {8,10,15,20c} x EARLY-CROSS timing (proxy via exit field)
  3. k-slot {<=9,<=10,<=11} x |sig| {<8,<10,<12} joint with depth
  4. EDGE-PROPORTIONAL sizing on clean boxes (size ~ lock-margin or ~ depth, capacity-capped)
  5. PRICE-REGION (favorite/balanced band) on top of depth gate
  6. BEST COMBINED config

All IS=first 60% / OOS=last 40%. Backtests SCREEN (fill model optimistic on strands).
Writes /tmp/rc_optimize/_edge_optimize_output.txt ; report assembled into EDGE_OPTIMIZE.md.
"""
from __future__ import annotations
import sys
sys.path.insert(0, '/tmp/rc_optimize')
import numpy as np
import pandas as pd
from ladder_baseline_study import load_parquet_windows
from pair_gate_study import (
    walk_gate, opening_fill_table, p_yeq, both_side_depth, disposal_value,
)

OUT = []
def pr(s=''):
    print(s)
    OUT.append(str(s))


# ------------------------------------------------------------
# Gate factory (same semantics as pair_gate_study.make_gate, extended with
# price-band + a sizing hook).  Depth threshold is ABSOLUTE dollars.
# ------------------------------------------------------------
def make_gate(min_depth=0.0, kmin=2, kmax=12, max_absig=1e9,
              max_div=1.0, pmin=0.0, pmax=1.0):
    def g(f):
        if both_side_depth(f) < min_depth:
            return False
        kk = f.get('k', 7)
        if kk < kmin or kk > kmax:
            return False
        if abs(f.get('sig', 0.0) or 0.0) > max_absig:
            return False
        if abs(p_yeq(f) - 0.5) > max_div:
            return False
        py = p_yeq(f)
        if py < pmin or py > pmax:
            return False
        return True
    return g


def summarize(fills, wl, gate, disposal='capcross', give_cap=0.15, n_total=None):
    r = walk_gate(fills, wl, gate=gate, disposal=disposal, give_cap=give_cap)
    traded = int(r['opened'].sum())
    nbox = len(r['box_pnls'])
    strand = r['strand'].sum() / max(traded, 1) * 100
    boxedge = r['box_pnls'].mean() * 100 if nbox else float('nan')
    netbox = r['pnl'].sum() / nbox * 100 if nbox else float('nan')
    px = r['pnl'][r['opened']]
    netwin = px.mean() * 100 if len(px) else float('nan')
    sh = px.mean() / px.std(ddof=1) if len(px) > 3 and px.std() > 0 else float('nan')
    nt = n_total if n_total else len(wl)
    return dict(traded=traded, traded_pct=traded / nt * 100, nbox=nbox,
                strand=strand, boxedge=boxedge, netbox=netbox, netwin=netwin,
                sh=sh, total=r['pnl'].sum() * 100)


# ------------------------------------------------------------
# Edge-proportional sizing walk (clean paired boxes scaled by margin/depth).
# Sizing applies ONLY to the box pnl (paired, risk-free capture); stranded legs
# carry their (sized) disposal. Capacity cap: size cannot exceed depth-implied cap.
# We replicate walk_gate's net-walk but with a per-open size multiplier.
# ------------------------------------------------------------
def walk_sized(fills_per_ws, ws_list, gate, size_fn, disposal='capcross', give_cap=0.15):
    pnl_arr = []
    strand_arr = []
    opened_any = []
    box_pnls = []          # raw (unsized) per-box edge, for reference
    box_pnls_sized = []
    sizes = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        net = 0
        pnl = 0.0
        open_leg = None
        open_sz = 1.0
        opened = False
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                box = f['settle'] + (open_leg['settle'] if open_leg else 0.0)
                pnl += open_sz * box
                box_pnls.append(box)
                box_pnls_sized.append(open_sz * box)
                sizes.append(open_sz)
                open_leg = None
                open_sz = 1.0
            else:
                if gate is not None and not gate(f):
                    continue
                open_leg = f
                open_sz = size_fn(f)
                opened = True
            net = nn
        stranded = open_leg is not None
        if stranded:
            dc = disposal_value(open_leg, disposal, give_cap)
            pnl += open_sz * dc
        pnl_arr.append(pnl)
        strand_arr.append(stranded)
        opened_any.append(opened)
    return dict(pnl=np.array(pnl_arr, float), strand=np.array(strand_arr, bool),
                opened=np.array(opened_any, bool),
                box_pnls=np.array(box_pnls, float),
                box_pnls_sized=np.array(box_pnls_sized, float),
                sizes=np.array(sizes, float))


def main():
    pr("=" * 78)
    pr("EDGE OPTIMIZATION STUDY (BTC 15m maker-box; pair-gate)")
    pr("=" * 78)

    fills, ws = load_parquet_windows('btc')
    n = len(ws)
    cut = int(n * 0.6)
    ws_is, ws_oos = ws[:cut], ws[cut:]
    pr(f"BTC windows={n}  IS={len(ws_is)} OOS={len(ws_oos)}")

    # Validated baseline reproduction
    pr("\n" + "=" * 78)
    pr("BASELINE (VALIDATED): depth>=33000 + k<=10 + |sig|<10, capcross give-cap 15c")
    pr("=" * 78)
    base_gate = make_gate(min_depth=33000, kmax=10, max_absig=10)
    for lbl, wl in [("FULL", ws), ("IS", ws_is), ("OOS", ws_oos)]:
        s = summarize(fills, wl, base_gate, give_cap=0.15, n_total=(n if lbl == "FULL" else None))
        pr(f"  [{lbl:4}] traded={s['traded_pct']:5.1f}% strand={s['strand']:4.1f}% "
           f"boxedge={s['boxedge']:+.3f}c net/box={s['netbox']:+.3f}c net/win={s['netwin']:+.3f}c Sh={s['sh']:+.3f}")
    BASE_NETBOX = summarize(fills, ws, base_gate, give_cap=0.15, n_total=n)['netbox']

    def row(name, s):
        pr(f"{name:<34} {s['traded_pct']:6.1f}% {s['strand']:5.1f}% {s['boxedge']:+7.3f}c "
           f"{s['netbox']:+7.3f}c {s['netwin']:+7.3f}c {s['nbox']:>6} {s['sh']:+6.3f}")

    def hdr():
        pr(f"{'config':<34} {'trade%':>6} {'strnd':>5} {'boxedg':>8} {'net/box':>8} {'net/win':>8} {'nbox':>6} {'Sh':>6}")
        pr("-" * 96)

    # ============================================================
    # SWEEP 1: DEPTH THRESHOLD  (k<=10, |sig|<10, give-cap 15c held fixed)
    # ============================================================
    pr("\n" + "=" * 78)
    pr("SWEEP 1: DEPTH THRESHOLD  (k<=10, |sig|<10, give-cap 15c)")
    pr("=" * 78)
    hdr()
    depth_rows = {}
    for d in [15000, 25000, 33000, 50000, 75000]:
        g = make_gate(min_depth=d, kmax=10, max_absig=10)
        sf = summarize(fills, ws, g, give_cap=0.15, n_total=n)
        si = summarize(fills, ws_is, g, give_cap=0.15)
        so = summarize(fills, ws_oos, g, give_cap=0.15)
        depth_rows[d] = (sf, si, so)
        row(f"depth>={d//1000}k FULL", sf)
        pr(f"{'    IS/OOS net/box':<34} {'':>6} {'':>5} {'':>8} "
           f"{si['netbox']:+7.3f}c/{so['netbox']:+.3f}c   strand IS/OOS {si['strand']:.1f}/{so['strand']:.1f}%")
    pr("\n  net-maximizing (net/box x nbox = total cents captured):")
    for d, (sf, si, so) in depth_rows.items():
        pr(f"    depth>={d//1000}k: total={sf['total']:+.1f}c  net/box={sf['netbox']:+.3f}c  net/win={sf['netwin']:+.3f}c  boxes={sf['nbox']}")

    # ============================================================
    # SWEEP 2: GIVE-CAP x EARLY-CROSS timing
    # ============================================================
    pr("\n" + "=" * 78)
    pr("SWEEP 2: GIVE-CAP (capcross) -- baseline gate depth>=33k k<=10 |sig|<10")
    pr("=" * 78)
    pr("  (early-cross timing is captured by the 'exit' field = sell-back ~1min later at touch;")
    pr("   we sweep the give-cap that decides cross-vs-hold on residual strands)")
    hdr()
    cap_rows = {}
    for cap in [0.08, 0.10, 0.15, 0.20]:
        sf = summarize(fills, ws, base_gate, give_cap=cap, n_total=n)
        si = summarize(fills, ws_is, base_gate, give_cap=cap)
        so = summarize(fills, ws_oos, base_gate, give_cap=cap)
        cap_rows[cap] = (sf, si, so)
        row(f"give-cap {int(cap*100)}c FULL", sf)
        pr(f"{'    IS/OOS net/box':<34} {'':>6} {'':>5} {'':>8} "
           f"{si['netbox']:+7.3f}c/{so['netbox']:+.3f}c")
    # also pure hold and pure early for reference
    for mode, lbl in [('hold', 'pure HOLD (settle)'), ('early', 'pure EARLY (cross)')]:
        sf = summarize(fills, ws, base_gate, disposal=mode, n_total=n)
        row(lbl, sf)

    # Disposal cost detail on residual strands
    df = opening_fill_table(fills, ws)
    sl = df[df['this_leg_strand'] == 1]
    pr(f"\n  Residual stranded legs (no-gate basis n={len(sl)}):")
    pr(f"    HOLD mean={sl['settle'].mean()*100:+.2f}c worst={sl['settle'].min()*100:+.1f}c")
    pr(f"    EARLY mean={sl['exit'].mean()*100:+.2f}c worst={sl['exit'].min()*100:+.1f}c")

    # ============================================================
    # SWEEP 3: k-slot x |sig| joint with depth
    # ============================================================
    pr("\n" + "=" * 78)
    pr("SWEEP 3: k-slot x |sig| (depth>=33k, give-cap 15c)")
    pr("=" * 78)
    hdr()
    k_sig_rows = {}
    for kmax in [9, 10, 11]:
        for sig in [8, 10, 12]:
            g = make_gate(min_depth=33000, kmax=kmax, max_absig=sig)
            sf = summarize(fills, ws, g, give_cap=0.15, n_total=n)
            si = summarize(fills, ws_is, g, give_cap=0.15)
            so = summarize(fills, ws_oos, g, give_cap=0.15)
            k_sig_rows[(kmax, sig)] = (sf, si, so)
            row(f"k<={kmax} |sig|<{sig}", sf)
    pr("\n  IS/OOS stability (net/box IS vs OOS) for k x sig:")
    for (kmax, sig), (sf, si, so) in k_sig_rows.items():
        gap = si['netbox'] - so['netbox']
        pr(f"    k<={kmax} |sig|<{sig}: IS={si['netbox']:+.3f}c OOS={so['netbox']:+.3f}c gap={gap:+.3f}c trade={sf['traded_pct']:.0f}%")

    # ============================================================
    # SWEEP 4: EDGE-PROPORTIONAL SIZING on clean boxes
    # ============================================================
    pr("\n" + "=" * 78)
    pr("SWEEP 4: EDGE-PROPORTIONAL SIZING (baseline gate; capcross 15c)")
    pr("=" * 78)
    pr("  Size the opening leg by lock-margin or by book depth, capped by capacity.")
    pr("  lock-margin proxy = box capture available = (1 - (p_yes_touch + p_no_touch)) i.e. how")
    pr("  far inside fair the paired box locks; deeper book = more capacity to size into.")

    # depth-based capacity cap: max contracts ~ depth / per-contract notional.
    # Kalshi contracts are $1 max; depth is displayed $ size. Cap multiplier so that
    # sized notional <= a fraction of displayed depth. We use a conservative cap of 3x base.
    def size_margin(f, lo=33000):
        # margin = how cheap the box locks: larger spread/edge -> size up. Use box-edge proxy
        # via -(p_touch deviation). We approximate per-leg edge by (0.5 spread capture).
        sp = f.get('spread', 0.01) or 0.01
        m = 1.0 + min(2.0, sp / 0.01 - 1.0)   # spread 1c->1x, 2c->2x, 3c+->3x(cap)
        return m

    def size_depth(f, ref=33000):
        d = both_side_depth(f)
        # scale 1x at 33k up to 3x at >=99k, capped (don't exceed displayed depth capacity)
        return float(np.clip(d / ref, 1.0, 3.0))

    pr("\n  [A] size ~ lock-margin (spread):")
    hdr()
    for lbl, sfn in [("flat 1x (ref)", lambda f: 1.0),
                     ("size~margin(spread)", size_margin),
                     ("size~depth(33k ref)", size_depth)]:
        # full
        for wlabel, wl, nt in [("FULL", ws, n)]:
            r = walk_sized(fills, wl, base_gate, sfn, give_cap=0.15)
            traded = int(r['opened'].sum())
            nbox = len(r['box_pnls'])
            # net/win normalised per OPENED window; net/box per box; but with sizing,
            # "net/box" = total pnl / number of boxes (effective $ per box of capital deployed).
            strand = r['strand'].sum() / max(traded, 1) * 100
            netbox = r['pnl'].sum() / nbox * 100 if nbox else float('nan')
            px = r['pnl'][r['opened']]
            netwin = px.mean() * 100 if len(px) else float('nan')
            # capital-weighted net/win: total pnl / total size deployed
            tot_sz = r['sizes'].sum()
            netper_unit = r['pnl'].sum() / tot_sz * 100 if tot_sz else float('nan')
            sh = px.mean() / px.std(ddof=1) if len(px) > 3 and px.std() > 0 else float('nan')
            pr(f"{lbl:<34} {traded/nt*100:6.1f}% {strand:5.1f}% {'':>8} "
               f"{netbox:+7.3f}c {netwin:+7.3f}c {nbox:>6} {sh:+6.3f}  net/unit={netper_unit:+.3f}c")
    pr("  NOTE: net/win rises with sizing only if it concentrates capital on +EV boxes;")
    pr("        net/UNIT (pnl / total contracts) is the unbiased risk-free-capture metric.")

    # IS/OOS for the best sizing variant
    pr("\n  IS/OOS for size~depth:")
    for lbl, wl in [("IS", ws_is), ("OOS", ws_oos)]:
        r = walk_sized(fills, wl, base_gate, size_depth, give_cap=0.15)
        nbox = len(r['box_pnls'])
        tot_sz = r['sizes'].sum()
        netbox = r['pnl'].sum() / nbox * 100 if nbox else float('nan')
        netunit = r['pnl'].sum() / tot_sz * 100 if tot_sz else float('nan')
        pr(f"    [{lbl}] net/box={netbox:+.3f}c net/unit={netunit:+.3f}c boxes={nbox}")

    # ============================================================
    # SWEEP 5: PRICE-REGION / favorite band on top of depth gate
    # ============================================================
    pr("\n" + "=" * 78)
    pr("SWEEP 5: PRICE-REGION (p_yes band) on top of depth>=33k k<=10 |sig|<10")
    pr("=" * 78)
    hdr()
    band_rows = {}
    bands = {
        "all (0-1)": (0.0, 1.0),
        "balanced .35-.65": (0.35, 0.65),
        "balanced .40-.60": (0.40, 0.60),
        "favorite .55-.85": (0.55, 0.85),
        "underdog .15-.45": (0.15, 0.45),
        "extreme-out .25-.75": (0.25, 0.75),
    }
    for lbl, (pmin, pmax) in bands.items():
        g = make_gate(min_depth=33000, kmax=10, max_absig=10, pmin=pmin, pmax=pmax)
        sf = summarize(fills, ws, g, give_cap=0.15, n_total=n)
        si = summarize(fills, ws_is, g, give_cap=0.15)
        so = summarize(fills, ws_oos, g, give_cap=0.15)
        band_rows[lbl] = (sf, si, so)
        row(lbl, sf)
        pr(f"{'    IS/OOS net/box':<34} {'':>6} {'':>5} {'':>8} "
           f"{si['netbox']:+7.3f}c/{so['netbox']:+.3f}c")

    # ============================================================
    # SWEEP 6: BEST COMBINED
    # ============================================================
    pr("\n" + "=" * 78)
    pr("SWEEP 6: BEST COMBINED CONFIG SEARCH (maximize net/box NET of volume, IS/OOS stable)")
    pr("=" * 78)
    pr("  Criterion: net/box maximized subject to OOS net/box>0, |IS-OOS gap|<0.25c,")
    pr("  traded>=20% (meaningful volume), strand<4%.")
    hdr()
    combos = {}
    cand = []
    for d in [33000, 50000, 75000]:
        for kmax in [9, 10]:
            for sig in [8, 10]:
                for band_lbl, (pmin, pmax) in [("all", (0.0, 1.0)), (".35-.65", (0.35, 0.65)), (".40-.60", (0.40, 0.60))]:
                    for cap in [0.10, 0.15]:
                        g = make_gate(min_depth=d, kmax=kmax, max_absig=sig, pmin=pmin, pmax=pmax)
                        sf = summarize(fills, ws, g, give_cap=cap, n_total=n)
                        si = summarize(fills, ws_is, g, give_cap=cap)
                        so = summarize(fills, ws_oos, g, give_cap=cap)
                        name = f"d{d//1000}k k{kmax} s{sig} p{band_lbl} c{int(cap*100)}"
                        combos[name] = (sf, si, so)
                        gap = abs(si['netbox'] - so['netbox'])
                        viable = (so['netbox'] > 0 and gap < 0.25 and sf['traded_pct'] >= 20
                                  and sf['strand'] < 4.0 and np.isfinite(sf['netbox']))
                        cand.append((name, sf, si, so, gap, viable))
    # rank viable by full net/box
    viable = [c for c in cand if c[5]]
    viable.sort(key=lambda c: -c[1]['netbox'])
    pr("  Top viable combos (net/box, IS/OOS stable):")
    for name, sf, si, so, gap, _ in viable[:12]:
        pr(f"    {name:<30} net/box={sf['netbox']:+.3f}c (IS {si['netbox']:+.3f}/OOS {so['netbox']:+.3f} gap {gap:.3f}) "
           f"trade={sf['traded_pct']:.0f}% strand={sf['strand']:.1f}% net/win={sf['netwin']:+.3f}c boxes={sf['nbox']}")

    best = viable[0] if viable else None
    if best:
        name, sf, si, so, gap, _ = best
        pr(f"\n  *** BEST COMBINED: {name} ***")
        pr(f"      net/box={sf['netbox']:+.3f}c (vs baseline {BASE_NETBOX:+.3f}c, "
           f"delta {sf['netbox']-BASE_NETBOX:+.3f}c)")
        pr(f"      IS net/box={si['netbox']:+.3f}c  OOS net/box={so['netbox']:+.3f}c  gap={gap:.3f}c")
        pr(f"      net/win={sf['netwin']:+.3f}c  trade%={sf['traded_pct']:.1f}  strand={sf['strand']:.1f}%  boxes={sf['nbox']}")

    # ============================================================
    # CROSS-ASSET check of baseline + best
    # ============================================================
    pr("\n" + "=" * 78)
    pr("CROSS-ASSET CHECK (ETH/SOL/XRP): baseline gate, give-cap 15c")
    pr("=" * 78)
    for asset in ['eth', 'sol', 'xrp']:
        try:
            fa, wa = load_parquet_windows(asset)
            na = len(wa)
            s = summarize(fa, wa, base_gate, give_cap=0.15, n_total=na)
            pr(f"  [{asset.upper()}] traded={s['traded_pct']:.1f}% strand={s['strand']:.1f}% "
               f"boxedge={s['boxedge']:+.3f}c net/box={s['netbox']:+.3f}c net/win={s['netwin']:+.3f}c boxes={s['nbox']}")
        except Exception as e:
            pr(f"  [{asset.upper()}] failed: {e}")

    with open('/tmp/rc_optimize/_edge_optimize_output.txt', 'w') as fh:
        fh.write("\n".join(OUT))
    pr("\nDone -> _edge_optimize_output.txt")


if __name__ == '__main__':
    main()
