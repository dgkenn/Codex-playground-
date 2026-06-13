"""eth_native_study.py -- ETH-NATIVE optimized box stack.

Tests the operator's hypothesis: can ETH's WIDE boxes (median +2.0c) be made net-positive
by (a) predicting & avoiding the toxic negative-margin tail AT ENTRY and (b) aggressively
cutting the unpaired leg with ETH-tuned thresholds + cross-asset hedge?

CRUX: is ETH box toxicity PREDICTABLE AT ENTRY (avoidable => hypothesis wins) or INTRINSIC
TO COMPLETION (a box completes precisely because price ran adversely => only knowable after
the fact => hypothesis fails)? This is the adverse-selection core, tested directly.

IS=first 60%, OOS=last 40%. Reuses ladder_baseline_study + box_policy_ab harness.

Writes ETH_NATIVE.md.
"""
from __future__ import annotations
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '/tmp/eth_native')
import numpy as np
import ladder_baseline_study as L
from box_policy_ab import _live_open_ok, hedge_unpaired

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


def fav_prob(f):
    py = f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)
    return max(py, 1.0 - py)


def yeq(f):
    return f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)


def window_meansig(fills):
    s = [abs(f.get('sig', 0.0) or 0.0) for f in fills]
    return float(np.mean(s)) if s else 0.0


def auc(probs, labels):
    from scipy.stats import rankdata
    labels = np.asarray(labels, int)
    n1 = labels.sum(); n0 = len(labels) - n1
    if n1 == 0 or n0 == 0:
        return 0.5
    r = rankdata(probs)
    return (r[labels == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


# ============================================================
# Box-level dataset: each COMPLETED box (both legs filled under P0
# always-pair walk) -> (margin, ENTRY-time features of the OPENING leg).
# Entry features are KNOWN at the moment we decide to open the first leg.
# ============================================================

def box_dataset(fills_per_ws, ws_list):
    """Return list of dicts: one per completed box, with entry features + margin.

    A box = an opening leg followed by a pairing leg (net returns to 0).
    We record the OPENING leg's decision-time features and the box's lock margin.
    Also returns count of stranded windows.
    """
    rows = []
    strand_windows = 0
    for ws in ws_list:
        fills = fills_per_ws[ws]
        wsig = window_meansig(fills)
        net = 0; open_leg = None
        boxed_this_window = False
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                # pairing leg
                if open_leg is not None:
                    margin = f['settle'] + open_leg['settle']
                    o = open_leg
                    rows.append(dict(
                        ws=ws, margin=margin,
                        spread=o.get('spread', 0.02),
                        absdev=abs(yeq(o) - 0.5),
                        favp=fav_prob(o),
                        sig=o.get('sig', 0.0) or 0.0,
                        abssig=abs(o.get('sig', 0.0) or 0.0),
                        flow=o.get('flow', 0.0) or 0.0,
                        absflow=abs(o.get('flow', 0.0) or 0.0),
                        k=float(o.get('k', 7)),
                        tau=o.get('tau', 0.5),
                        vpin=(o.get('vpin') if o.get('vpin') is not None
                              and not (isinstance(o.get('vpin'), float) and np.isnan(o.get('vpin')))
                              else np.nan),
                        depth=o.get('depth', np.nan),
                        wsig=wsig,
                        side_bid=1.0 if o['side'] == 'bid' else 0.0,
                    ))
                    boxed_this_window = True
                open_leg = None
            else:
                open_leg = f
            net = nn
        if open_leg is not None:
            strand_windows += 1
    return rows, strand_windows


FEATS = ['spread', 'absdev', 'favp', 'sig', 'abssig', 'flow', 'absflow',
         'k', 'tau', 'vpin', 'depth', 'wsig', 'side_bid']


def to_matrix(rows, feats=FEATS):
    X = np.array([[r[f] for f in feats] for r in rows], float)
    y = np.array([1 if r['margin'] < 0 else 0 for r in rows], int)  # 1 = TOXIC
    return X, y


def fill_nan(X, means=None):
    if means is None:
        means = np.nanmean(X, axis=0)
    Xf = X.copy()
    for j in range(X.shape[1]):
        Xf[np.isnan(Xf[:, j]), j] = means[j]
    return Xf, means


def decomp_section(rows, label):
    m = np.array([r['margin'] for r in rows], float)
    print(f"\n[{label}] completed boxes n={len(m)}")
    print(f"  mean={m.mean()*100:+.2f}c median={np.median(m)*100:+.2f}c "
          f"std={m.std()*100:.2f}c neg%={(m<0).mean()*100:.1f}")
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        print(f"    p{p:<2}={np.percentile(m, p)*100:+7.2f}c", end='')
        if p in (5, 50, 95):
            print()
    print()
    return m


def char_tail(rows, label):
    """Characterize toxic vs clean boxes by entry features."""
    m = np.array([r['margin'] for r in rows], float)
    tox = m < 0
    print(f"\n[{label}] TOXIC ({tox.mean()*100:.1f}%) vs CLEAN entry-feature means:")
    print(f"  {'feature':<10} {'toxic':>10} {'clean':>10} {'sep(t)':>8}")
    from scipy.stats import ttest_ind
    for f in FEATS:
        v = np.array([r[f] for r in rows], float)
        mt = ~np.isnan(v)
        vt = v[mt & tox]; vc = v[mt & ~tox]
        if len(vt) < 5 or len(vc) < 5:
            continue
        try:
            t = ttest_ind(vt, vc, equal_var=False).statistic
        except Exception:
            t = float('nan')
        print(f"  {f:<10} {vt.mean():>10.3f} {vc.mean():>10.3f} {t:>8.2f}")


def slice_margins(rows, name, mask_fn):
    m = np.array([r['margin'] for r in rows], float)
    mask = np.array([mask_fn(r) for r in rows], bool)
    if mask.sum() == 0:
        print(f"  {name:<34} n=0"); return None
    mm = m[mask]
    print(f"  {name:<34} n={mask.sum():5} ({mask.mean()*100:4.1f}%) "
          f"mean={mm.mean()*100:+7.2f}c neg%={(mm<0).mean()*100:4.1f} median={np.median(mm)*100:+6.2f}c")
    return mm


def main():
    print("=" * 90)
    print("ETH-NATIVE STUDY")
    print("=" * 90)
    fe, we = L.load_parquet_windows('eth')
    cut = int(len(we) * 0.6)
    ws_is, ws_oos = we[:cut], we[cut:]
    print(f"ETH windows={len(we)} IS={len(ws_is)} OOS={len(ws_oos)}")

    rows_all, strand_all = box_dataset(fe, we)
    rows_is, strand_is = box_dataset(fe, ws_is)
    rows_oos, strand_oos = box_dataset(fe, ws_oos)

    # ===== TASK 1: DECOMPOSE =====
    print("\n" + "=" * 90)
    print("TASK 1: MARGIN DISTRIBUTION DECOMPOSITION")
    print("=" * 90)
    m_all = decomp_section(rows_all, "ALL")
    decomp_section(rows_is, "IS")
    decomp_section(rows_oos, "OOS")
    print(f"\nStrand windows: ALL={strand_all}/{len(we)} ({strand_all/len(we)*100:.1f}%) "
          f"OOS={strand_oos}/{len(ws_oos)} ({strand_oos/len(ws_oos)*100:.1f}%)")
    print(f"Positive-margin fraction: {(m_all>=0).mean()*100:.1f}%  "
          f"Fat positive: p75={np.percentile(m_all,75)*100:+.1f}c p90={np.percentile(m_all,90)*100:+.1f}c")

    char_tail(rows_all, "ALL")

    print("\n--- SLICE MARGINS (entry-knowable cuts, ALL) ---")
    slice_margins(rows_all, "thin spread (<2c)", lambda r: r['spread'] < 0.02)
    slice_margins(rows_all, "wide spread (>=2c)", lambda r: r['spread'] >= 0.02)
    slice_margins(rows_all, "wide spread (>=3c)", lambda r: r['spread'] >= 0.03)
    slice_margins(rows_all, "early k<5", lambda r: r['k'] < 5)
    slice_margins(rows_all, "mid k5-9", lambda r: 5 <= r['k'] <= 9)
    slice_margins(rows_all, "late k>9", lambda r: r['k'] > 9)
    slice_margins(rows_all, "deep fav >0.70", lambda r: r['favp'] > 0.70)
    slice_margins(rows_all, "deep fav >0.80", lambda r: r['favp'] > 0.80)
    slice_margins(rows_all, "non-fav <=0.70", lambda r: r['favp'] <= 0.70)
    slice_margins(rows_all, "low |sig| (<3bps)", lambda r: r['abssig'] < 3)
    slice_margins(rows_all, "hi |sig| (>8bps)", lambda r: r['abssig'] > 8)
    slice_margins(rows_all, "low wsig (<3)", lambda r: r['wsig'] < 3)
    slice_margins(rows_all, "hi wsig (>8)", lambda r: r['wsig'] > 8)
    slice_margins(rows_all, "hi vpin (>0.5)", lambda r: not np.isnan(r['vpin']) and r['vpin'] > 0.5)
    slice_margins(rows_all, "lo vpin (<0.35)", lambda r: not np.isnan(r['vpin']) and r['vpin'] < 0.35)

    # ===== TASK 2: PREDICTABILITY =====
    print("\n" + "=" * 90)
    print("TASK 2: ENTRY-TIME TOXICITY PREDICTABILITY (the crux)")
    print("=" * 90)
    X_is, y_is = to_matrix(rows_is)
    X_oos, y_oos = to_matrix(rows_oos)
    X_isf, means = fill_nan(X_is)
    X_oosf, _ = fill_nan(X_oos, means)
    print(f"IS toxic rate={y_is.mean()*100:.1f}%  OOS toxic rate={y_oos.mean()*100:.1f}%")

    gbm = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05,
                                     subsample=0.8, random_state=42)
    gbm.fit(X_isf, y_is)
    p_is = gbm.predict_proba(X_isf)[:, 1]
    p_oos = gbm.predict_proba(X_oosf)[:, 1]
    print(f"\nGBM  IS-AUC={auc(p_is,y_is):.3f}  OOS-AUC={auc(p_oos,y_oos):.3f}")

    sc = StandardScaler().fit(X_isf)
    lr = LogisticRegression(max_iter=1000, C=1.0).fit(sc.transform(X_isf), y_is)
    lp_is = lr.predict_proba(sc.transform(X_isf))[:, 1]
    lp_oos = lr.predict_proba(sc.transform(X_oosf))[:, 1]
    print(f"Logit IS-AUC={auc(lp_is,y_is):.3f}  OOS-AUC={auc(lp_oos,y_oos):.3f}")

    print("\nGBM feature importances:")
    for f, imp in sorted(zip(FEATS, gbm.feature_importances_), key=lambda x: -x[1]):
        print(f"  {f:<10} {imp:.3f}")

    # Calibration: if we gate at various predicted-toxicity thresholds, what
    # happens to the SURVIVING boxes' mean margin & count? (decision-relevant)
    print("\n--- GATE CALIBRATION (OOS): keep boxes with p_tox <= thresh ---")
    m_oos = np.array([r['margin'] for r in rows_oos], float)
    print(f"  {'thresh':>7} {'kept':>7} {'keep%':>7} {'mean_c':>9} {'neg%':>6}")
    for thr in [1.0, 0.5, 0.4, 0.35, 0.3, 0.25, 0.2]:
        keep = p_oos <= thr
        if keep.sum() == 0:
            print(f"  {thr:>7.2f} {0:>7} {0:>7.1f}"); continue
        mk = m_oos[keep]
        print(f"  {thr:>7.2f} {keep.sum():>7} {keep.mean()*100:>6.1f}% "
              f"{mk.mean()*100:>+8.2f}c {(mk<0).mean()*100:>5.1f}%")

    return fe, we, ws_is, ws_oos, rows_all, rows_is, rows_oos, gbm, means


if __name__ == '__main__':
    main()
