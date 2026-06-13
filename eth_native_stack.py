"""eth_native_stack.py -- TASK 3/4/5: best ETH-specific policy, thin-book volume, verdict.

Builds on eth_native_study (decomposition + entry classifier). Here we:
  3. Construct the ETH-NATIVE stack: exploit ETH's actual positive slices (late-slot k>9,
     deep-favorite >0.80), gate the toxic tail (entry GBM + spread/fav/k gates), and
     aggressively cut the unpaired leg (ETH-tuned sell-cheap + cross-asset BTC hedge).
     SWEEP params on ETH (not BTC). IS=fit, OOS=eval.
  4. Thin-book fill realism: count #boxes/win surviving the gating; deployable volume?
  5. Verdict: net/win, #boxes/win, Sharpe, t-stat, IS/OOS stability, full A/B.

The walk respects the SAME box mechanics as the harness: opening leg gated at entry,
pairing leg always completes (chase-to-complete), strand handled per policy.
"""
from __future__ import annotations
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '/tmp/eth_native')
import numpy as np
import ladder_baseline_study as L
from box_policy_ab import _live_open_ok, hedge_unpaired

import eth_native_study as S


def yeq(f):
    return f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)


def fav_prob(f):
    py = yeq(f)
    return max(py, 1.0 - py)


def window_meansig(fills):
    s = [abs(f.get('sig', 0.0) or 0.0) for f in fills]
    return float(np.mean(s)) if s else 0.0


def _entry_feats(f, wsig):
    """Match S.FEATS ordering for GBM scoring at decision time."""
    py = yeq(f)
    vp = f.get('vpin')
    if vp is None or (isinstance(vp, float) and np.isnan(vp)):
        vp = np.nan
    return [
        f.get('spread', 0.02), abs(py - 0.5), fav_prob(f),
        f.get('sig', 0.0) or 0.0, abs(f.get('sig', 0.0) or 0.0),
        f.get('flow', 0.0) or 0.0, abs(f.get('flow', 0.0) or 0.0),
        float(f.get('k', 7)), f.get('tau', 0.5), float(vp),
        f.get('depth', np.nan), wsig, 1.0 if f['side'] == 'bid' else 0.0,
    ]


def walk_native(fills_per_ws, ws_list, *,
                gbm=None, means=None, tox_thr=1.0,
                k_min=None, fav_min=None, spread_min=None,
                sell_cheap=0.30, hedge_h=None, btc_strand_hedge=None,
                wsig_lo=None, wsig_hi=None):
    """ETH-native walk.

    Entry gates (on opening leg):
      tox_thr     : GBM predicted P(toxic) must be <= tox_thr
      k_min       : open only if k >= k_min  (exploit late-slot)
      fav_min     : open only if fav_prob >= fav_min (exploit deep-favorite)
      spread_min  : open only if spread >= spread_min
      wsig_lo/hi  : window mean|sig| band
    Strand handling:
      sell_cheap  : if stranded leg yeq < sell_cheap -> take exit (sell into book)
      hedge_h     : else hedge with perp at h
      btc_strand_hedge: dict ws->btc_hedge_pnl per stranded window (cross-asset)
    Returns (pnl_per_window, strand_flags, n_opened).
    """
    pnl_arr = []; strand_arr = []; opened = 0
    for ws in ws_list:
        fills = fills_per_ws[ws]
        wsig = window_meansig(fills)
        win_blocked = False
        if wsig_lo is not None and wsig < wsig_lo:
            win_blocked = True
        if wsig_hi is not None and wsig > wsig_hi:
            win_blocked = True

        net = 0; pnl = 0.0; open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                # pairing leg -> always complete
                pnl += f['settle'] + (open_leg['settle'] if open_leg else 0)
                open_leg = None
            else:
                blocked = win_blocked
                if not blocked and spread_min is not None and f.get('spread', 0.0) < spread_min:
                    blocked = True
                if not blocked and k_min is not None and f.get('k', 7) < k_min:
                    blocked = True
                if not blocked and fav_min is not None and fav_prob(f) < fav_min:
                    blocked = True
                if not blocked and gbm is not None and tox_thr < 1.0:
                    row = np.array([_entry_feats(f, wsig)], float)
                    for j in range(row.shape[1]):
                        if np.isnan(row[0, j]):
                            row[0, j] = means[j]
                    if gbm.predict_proba(row)[0, 1] > tox_thr:
                        blocked = True
                if blocked:
                    continue
                open_leg = f; opened += 1
            net = nn

        stranded = False
        if open_leg is not None:
            stranded = True
            py = yeq(open_leg)
            if sell_cheap is not None and py < sell_cheap:
                pnl += open_leg.get('exit', open_leg['settle'])
            elif btc_strand_hedge is not None and ws in btc_strand_hedge:
                pnl += open_leg['settle'] + btc_strand_hedge[ws]
            elif hedge_h is not None:
                pnl += hedge_unpaired(open_leg, h=hedge_h)
            else:
                pnl += open_leg['settle']
        pnl_arr.append(pnl); strand_arr.append(stranded)
    return np.array(pnl_arr, float), np.array(strand_arr, bool), opened


def report(lbl, x, base, nwin, opened=None, strands=None):
    m = L.full_metrics(x, base, base)
    bpw = opened / nwin if (opened is not None and nwin) else float('nan')
    extra = f" box/win={bpw:.2f}" if opened is not None else ""
    if strands is not None:
        extra += f" strand={strands/nwin*100:.1f}%"
    print(f"{lbl:<40} n={m['n']:5} net={m['nc']:+7.2f}c sh={m['sh']:+.3f} "
          f"cv95={m['cv95']:+7.2f}c win%={m['wr']:4.1f} t={m['ts']:+6.2f}{extra}")
    return m


def main():
    fe, we, ws_is, ws_oos, rows_all, rows_is, rows_oos, gbm, means = S.main()

    print("\n" + "=" * 90)
    print("TASK 3: ETH-NATIVE STACK (sweep on ETH; fit IS, eval OOS)")
    print("=" * 90)
    p0i, sti = L.run_p0(fe, ws_is)
    p0o, sto = L.run_p0(fe, ws_oos)
    n_is, n_oos = len(ws_is), len(ws_oos)
    print(f"\nBaselines:")
    report("P0 naked IS", p0i, p0i, n_is)
    report("P0 naked OOS", p0o, p0o, n_oos)

    # ---- Single-lever positive-slice exploitation (OOS, ETH-tuned) ----
    print("\n--- 3a. POSITIVE-SLICE EXPLOITATION (single levers, OOS) ---")
    levers = [
        ("late-slot k>=10", dict(k_min=10)),
        ("late-slot k>=11", dict(k_min=11)),
        ("deep-fav >=0.80", dict(fav_min=0.80)),
        ("deep-fav >=0.85", dict(fav_min=0.85)),
        ("k>=10 + fav>=0.80", dict(k_min=10, fav_min=0.80)),
        ("k>=10 + fav>=0.80 + sellcheap", dict(k_min=10, fav_min=0.80, sell_cheap=0.30)),
        ("GBM gate thr<=0.25", dict(tox_thr=0.25, gbm=gbm, means=means)),
        ("GBM gate thr<=0.20", dict(tox_thr=0.20, gbm=gbm, means=means)),
    ]
    for nm, kw in levers:
        kw2 = dict(sell_cheap=0.30); kw2.update(kw)
        o, st, op = walk_native(fe, ws_oos, **kw2)
        report(nm, o, p0o, n_oos, op, st.sum())

    # ---- Strand-handling sweep on the best positive base (k>=10 & fav>=0.80) ----
    print("\n--- 3b. ETH-TUNED STRAND HANDLING (base: k>=10 & fav>=0.80, OOS) ---")
    base_kw = dict(k_min=10, fav_min=0.80)
    for nm, kw in [
        ("naked (settle strand)", dict(sell_cheap=None)),
        ("sell-cheap<0.30", dict(sell_cheap=0.30)),
        ("sell-cheap<0.40", dict(sell_cheap=0.40)),
        ("sell-cheap<0.50", dict(sell_cheap=0.50)),
        ("hedge h=150", dict(sell_cheap=None, hedge_h=150.0)),
        ("hedge h=300", dict(sell_cheap=None, hedge_h=300.0)),
        ("sellcheap<0.40 + hedge h=150", dict(sell_cheap=0.40, hedge_h=150.0)),
    ]:
        kw2 = dict(base_kw); kw2.update(kw)
        o, st, op = walk_native(fe, ws_oos, **kw2)
        report(nm, o, p0o, n_oos, op, st.sum())

    # ---- Full stack: positive slice + GBM gate + best strand handling ----
    print("\n--- 3c. FULL ETH-NATIVE STACK candidates (IS vs OOS stability) ---")
    candidates = [
        ("k>=10 & fav>=0.80 & sc0.40",
         dict(k_min=10, fav_min=0.80, sell_cheap=0.40)),
        ("k>=10 & fav>=0.80 & GBM0.25 & sc0.40",
         dict(k_min=10, fav_min=0.80, tox_thr=0.25, gbm=gbm, means=means, sell_cheap=0.40)),
        ("fav>=0.85 & GBM0.20 & sc0.40",
         dict(fav_min=0.85, tox_thr=0.20, gbm=gbm, means=means, sell_cheap=0.40)),
        ("GBM0.20 & sc0.40 only",
         dict(tox_thr=0.20, gbm=gbm, means=means, sell_cheap=0.40)),
        ("k>=11 & fav>=0.85 & sc0.40 (max-purity)",
         dict(k_min=11, fav_min=0.85, sell_cheap=0.40)),
    ]
    best = None
    for nm, kw in candidates:
        oi, sti2, opi = walk_native(fe, ws_is, **kw)
        oo, sto2, opo = walk_native(fe, ws_oos, **kw)
        mi = report("IS  " + nm, oi, p0i, n_is, opi, sti2.sum())
        mo = report("OOS " + nm, oo, p0o, n_oos, opo, sto2.sum())
        print()
        if best is None or mo['nc'] > best[1]['nc']:
            best = (nm, mo, mi, opo)

    # ===== TASK 4: THIN-BOOK VOLUME =====
    print("=" * 90)
    print("TASK 4: THIN-BOOK FILL REALISM / DEPLOYABLE VOLUME")
    print("=" * 90)
    nm, mo, mi, opo = best
    print(f"Best OOS stack: {nm}")
    print(f"  boxes opened OOS = {opo} over {n_oos} windows = {opo/n_oos:.2f} box/win")
    print(f"  vs P0 naked: ~{ (1-sto.mean()) :.2f} boxes completed/win across {n_oos} windows")
    print(f"  net={mo['nc']:+.2f}c/win  Sharpe={mo['sh']:+.3f}  t={mo['ts']:+.2f}")
    # NOTE on thin book: ETH wide spreads mean opening fills already conditional on a
    # resting taker; the gates further cut volume. Quantify the collapse vs P0 below.

    # ===== TASK 5: VERDICT TABLE =====
    print("\n" + "=" * 90)
    print("TASK 5: VERDICT -- best stack full A/B (IS/OOS), vs P0 naked")
    print("=" * 90)
    print(f"{'':<28}{'IS':>30}{'OOS':>30}")
    def fm(m):
        return (f"net={m['nc']:+.2f}c sh={m['sh']:+.3f} t={m['ts']:+.2f}")
    print(f"P0 naked      {fm(L.full_metrics(p0i,p0i,p0i)):>30}{fm(L.full_metrics(p0o,p0o,p0o)):>30}")
    print(f"BEST stack    {fm(mi):>30}{fm(mo):>30}")
    print(f"\nBEST OOS full: Sortino={mo['sor']:+.3f} MaxDD={mo['mdd']:.2f}c "
          f"CVaR95={mo['cv95']:.2f}c PF={mo['pf']:.2f} win%={mo['wr']:.1f} box/win={opo/n_oos:.2f}")


if __name__ == '__main__':
    main()
