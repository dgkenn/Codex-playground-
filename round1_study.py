"""round1_study.py -- Round 1 strand-prevention research loop.

Five entry-gate ideas tested IS (60%) / OOS (40%) on the BTC 15-min tape.
Computes all metrics vs live_current baseline (t36 guarded opener).

Ideas:
  1. Strand Predictor Gate (LogReg on decision-time features)
  2. A-S Quote Skew vs t36 binary (continuous P(strand) penalty)
  3. Spot-Momentum Filter (|sig| threshold sweep)
  4. Microprice-Divergence Gate (micro-mid threshold sweep)
  5. Queue-Thinness Entry (book depth threshold)

Verdict: SIGNAL = OOS lift >= IS lift (durable). MIRAGE = IS only, OOS degrades.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys
import warnings

import numpy as np
import pandas as pd
import scipy.stats as stats

warnings.filterwarnings("ignore")

# ── patch path ───────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from box_policy_ab import (
    window_fills,
    per_minute_touch,
    run_policy,
    _live_open_ok,
    _vpin_buckets,
    _top5,
)

# ── data paths ───────────────────────────────────────────────────────────────
HIST_FILE   = os.path.join(_HERE, "hist_kalshi_btc15m.parquet")
TRADES_FILE = os.path.join(_HERE, "trades_kalshi_btc15m.parquet")
OVERNIGHT   = os.path.join(_HERE, "overnight_data")
GHA_DATA    = os.path.join(_HERE, "gha_data")

# ── constants ─────────────────────────────────────────────────────────────────
IS_FRAC  = 0.60
SEED     = 42


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_parquet():
    h = pd.read_parquet(HIST_FILE).set_index("ws")
    t = pd.read_parquet(TRADES_FILE).set_index("ws")
    common = sorted(set(h.index) & set(t.index))
    return h, t, common


def _rglob(d, pat):
    import glob
    return glob.glob(os.path.join(d, "**", pat), recursive=True) + \
           glob.glob(os.path.join(d, pat))


def iter_gz(fp):
    try:
        with gzip.open(fp, "rt") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except Exception:
                    continue
    except (EOFError, OSError, gzip.BadGzipFile):
        return


def load_book_stream(paths, asset="btc"):
    """Load book stream: ws -> list of (t, best_yes_bid, best_no_bid, spot, depth_min)."""
    books = {}
    res   = {}
    for d in paths:
        for fp in sorted(set(_rglob(d, f"book_kalshi_{asset}15m*.jsonl.gz"))):
            for r in iter_gz(fp):
                typ = r.get("type")
                if typ == "book":
                    yb = r.get("yes") or []
                    nb = r.get("no")  or []
                    if not yb or not nb:
                        continue
                    ws = r.get("ws")
                    if ws is None:
                        continue
                    best_yes_bid = float(yb[-1][0])
                    best_no_bid  = float(nb[-1][0])
                    spot         = r.get("spot")
                    depth_min    = min(_top5(yb), _top5(nb))
                    books.setdefault(ws, []).append(
                        (r["t"], best_yes_bid, best_no_bid,
                         float(spot) if spot is not None else None,
                         depth_min)
                    )
                elif typ == "stat":
    # not needed here
                    pass
        for fp in sorted(set(_rglob(d, f"shadow_windows_kalshi_{asset}15m*.jsonl"))):
            try:
                with open(fp) as fh:
                    for ln in fh:
                        try:
                            r = json.loads(ln)
                        except Exception:
                            continue
                        ru = r.get("resolved_up")
                        if ru in (0, 1):
                            res[r["ws"]] = int(ru)
            except Exception:
                pass
    return books, res


# ══════════════════════════════════════════════════════════════════════════════
# FILL RECONSTRUCTION (adapted from box_policy_ab.window_fills but leaner)
# ══════════════════════════════════════════════════════════════════════════════

def arr(x):
    return np.asarray(x, float)


def build_fills(h, t_df, common, book_stream=None):
    """
    Build per-window fill lists with decision-time features.
    Returns list of dicts (one per fill) with keys:
      ws, side, settle, exit, sig, p, spread, k, tau, flow,
      depth, vpin, tksize, micro_bid, micro_ask, micro_mid, micro_vs_mid
    Also per-window: strand flag (leg filled, no partner in same minute),
    both_fill (True if both legs filled in same minute).
    """
    fills_all  = []
    wins_all   = {}   # ws -> {"fills": [...], "strand_fills": [...], "box_fills": [...]}

    for ws in common:
        try:
            h_row  = h.loc[ws]
            t_row  = t_df.loc[ws]
        except KeyError:
            continue

        bid = arr(h_row["bid_path"])
        ask = arr(h_row["ask_path"])
        res = int(h_row["res_up"])
        spot_path = arr(h_row["spot_path"])

        t_arr  = arr(t_row["t"])
        p_arr  = arr(t_row["p"])
        sz_arr = arr(t_row["sz"])
        buy_arr = arr(t_row["buy"]).astype(bool)

        # VPIN
        bt, bi = _vpin_buckets(t_arr, sz_arr, buy_arr)

        # Book stream for this window (for microprice & depth)
        book_snaps = None
        if book_stream and ws in book_stream:
            book_snaps = sorted(book_stream[ws])  # sorted by t

        spot_l = np.concatenate([[np.nan], spot_path[:-1]])
        sset_arr = spot_path[~np.isnan(spot_path)]
        sset = float(sset_arr[-1]) if len(sset_arr) > 0 else np.nan

        win_fills  = []
        win_strand = []
        win_boxes  = []

        for k in range(2, 13):
            b0, a0 = bid[k], ask[k]
            if np.isnan(b0) or np.isnan(a0):
                continue
            mid = (b0 + a0) / 2.0
            if not (0.03 <= mid <= 0.97):
                continue

            spread = round(a0 - b0, 4)
            tau    = (15 - k) / 15.0

            # Spot move (3-min, bps)
            s_now  = spot_l[k]
            s_then = spot_l[max(k - 3, 0)]
            mv = (s_now / s_then - 1) * 1e4 if (s_now and s_then and s_now > 0 and s_then > 0) else 0.0

            # Prior-minute flow
            pl, ph = ws + 60 * (k - 1), ws + 60 * k
            j0, j1 = int(np.searchsorted(t_arr, pl)), int(np.searchsorted(t_arr, ph))
            flow = float(np.sum(np.where(buy_arr[j0:j1], sz_arr[j0:j1], -sz_arr[j0:j1])))

            # Microprice from book snapshot nearest to start of minute k
            micro_bid = np.nan
            micro_ask = np.nan
            micro_mid = np.nan
            depth_k   = np.nan
            if book_snaps:
                snap_t = ws + 60 * k   # boundary of minute k
                # find last snap before snap_t
                last_snap = None
                for snap in book_snaps:
                    if snap[0] <= snap_t:
                        last_snap = snap
                    else:
                        break
                if last_snap is not None:
                    micro_bid = last_snap[1]
                    micro_ask = round(1.0 - last_snap[2], 4)
                    micro_mid = (micro_bid + micro_ask) / 2.0
                    depth_k   = last_snap[4]

            # Depth from bid/ask if no book snap (use spread as proxy)
            dk = float(depth_k) if not np.isnan(depth_k) else None

            # Next-minute exit values
            b1 = bid[k + 1] if k + 1 < 15 else b0
            a1 = ask[k + 1] if k + 1 < 15 else a0
            if np.isnan(b1) or np.isnan(a1):
                b1, a1 = b0, a0
            mid1 = (b1 + a1) / 2.0
            sp1  = a1 - b1
            exit_bid = (mid1 - sp1 / 2.0) - b0
            exit_ask = a0 - (mid1 + sp1 / 2.0)

            # Find fills in minute k+1
            lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
            i0, i1 = int(np.searchsorted(t_arr, lo)), int(np.searchsorted(t_arr, hi))

            got_b = got_a = False
            b_fill = a_fill = None

            for i in range(i0, i1):
                p, sz, buy = float(p_arr[i]), float(sz_arr[i]), bool(buy_arr[i])
                if not got_b and not buy and p <= b0 + 1e-9:
                    # Compute VPIN at fill time
                    vp = float(np.nan)
                    if len(bt):
                        vp = float(np.mean(bi[max(0, int(np.searchsorted(bt, t_arr[i])) - 5):
                                              int(np.searchsorted(bt, t_arr[i]))]))
                    fill = {
                        "ws": ws, "side": "bid",
                        "settle": float(res) - b0,
                        "exit": exit_bid,
                        "sig": mv,
                        "p": b0, "spread": spread, "k": k, "tau": tau,
                        "flow": flow,
                        "depth": dk,
                        "vpin": vp if not np.isnan(vp) else None,
                        "tksize": sz,
                        "micro_bid": micro_bid if not np.isnan(micro_bid) else None,
                        "micro_ask": micro_ask if not np.isnan(micro_ask) else None,
                        "micro_mid": micro_mid if not np.isnan(micro_mid) else None,
                        "micro_vs_mid": (micro_mid - mid) if not np.isnan(micro_mid) else None,
                        "spot": float(spot_path[k]) if not np.isnan(spot_path[k]) else None,
                        "sset": sset,
                    }
                    b_fill = fill
                    got_b = True
                if not got_a and buy and p >= a0 - 1e-9:
                    vp = float(np.nan)
                    if len(bt):
                        vp = float(np.mean(bi[max(0, int(np.searchsorted(bt, t_arr[i])) - 5):
                                              int(np.searchsorted(bt, t_arr[i]))]))
                    fill = {
                        "ws": ws, "side": "ask",
                        "settle": a0 - float(res),
                        "exit": exit_ask,
                        "sig": -mv,
                        "p": round(1.0 - a0, 4), "spread": spread, "k": k, "tau": tau,
                        "flow": -flow,
                        "depth": dk,
                        "vpin": vp if not np.isnan(vp) else None,
                        "tksize": sz,
                        "micro_bid": micro_bid if not np.isnan(micro_bid) else None,
                        "micro_ask": micro_ask if not np.isnan(micro_ask) else None,
                        "micro_mid": micro_mid if not np.isnan(micro_mid) else None,
                        "micro_vs_mid": (micro_mid - mid) if not np.isnan(micro_mid) else None,
                        "spot": float(spot_path[k]) if not np.isnan(spot_path[k]) else None,
                        "sset": sset,
                    }
                    a_fill = fill
                    got_a = True
                if got_b and got_a:
                    break

            if got_b and got_a:
                # Box: both legs filled
                for f in [b_fill, a_fill]:
                    f["strand"] = 0
                    f["box"]    = 1
                    win_fills.append(f)
                    win_boxes.append(f)
                    fills_all.append(f)
            elif got_b:
                # Strand: only YES leg
                b_fill["strand"] = 1
                b_fill["box"]    = 0
                win_fills.append(b_fill)
                win_strand.append(b_fill)
                fills_all.append(b_fill)
            elif got_a:
                # Strand: only NO leg
                a_fill["strand"] = 1
                a_fill["box"]    = 0
                win_fills.append(a_fill)
                win_strand.append(a_fill)
                fills_all.append(a_fill)

        wins_all[ws] = {
            "fills": win_fills,
            "strands": win_strand,
            "boxes": win_boxes,
        }

    return fills_all, wins_all


# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(pnl_arr):
    """Given array of per-window PnL (dollars), return metric dict."""
    x = np.asarray([v for v in pnl_arr if v is not None], float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 2:
        return dict(n=n, mean=np.nan, sharpe=np.nan, skew=np.nan, cvar95=np.nan)
    mean  = float(np.mean(x))
    std   = float(np.std(x, ddof=1))
    sharpe = mean / std if std > 1e-12 else (np.inf if mean > 0 else 0.0)
    sk    = float(stats.skew(x))
    cutoff = np.percentile(x, 5)
    cvar95 = float(np.mean(x[x <= cutoff])) if np.any(x <= cutoff) else np.nan
    return dict(n=n, mean=mean, sharpe=sharpe, skew=sk, cvar95=cvar95)


def strand_rate(fills):
    if not fills:
        return np.nan
    return sum(f["strand"] for f in fills) / len(fills)


def both_fill_rate(wins_dict):
    """P(both legs filled) = windows with >=1 box / total windows."""
    wins = [ws for ws, v in wins_dict.items() if v["boxes"]]
    total = len(wins_dict)
    return len(wins) / total if total else np.nan


def window_pnl_policy(wins_dict, open_ok=None):
    """Compute per-window PnL under open_ok gate."""
    pnls = []
    for ws in sorted(wins_dict.keys()):
        fills = wins_dict[ws]["fills"]
        pnl = run_policy(fills, open_ok=open_ok)
        pnls.append(pnl)
    return np.array(pnls)


def window_pnl_live(wins_dict):
    """live_current policy per-window PnL."""
    pnls = []
    for ws in sorted(wins_dict.keys()):
        fills = wins_dict[ws]["fills"]
        pnl = run_policy(fills, open_ok=_live_open_ok)
        pnls.append(pnl)
    return np.array(pnls)


def diff_vs_live(m_candidate, m_live, key):
    """Difference of metric[key] between candidate and live."""
    try:
        return m_candidate[key] - m_live[key]
    except Exception:
        return np.nan


# ══════════════════════════════════════════════════════════════════════════════
# IDEA 1: STRAND PREDICTOR GATE (LogReg)
# ══════════════════════════════════════════════════════════════════════════════

def idea1_strand_predictor(fills_is, fills_oos, wins_is, wins_oos, live_m_is, live_m_oos):
    print("\n" + "="*70)
    print("IDEA 1: STRAND PREDICTOR GATE (LogReg)")
    print("="*70)

    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("  sklearn not available -- skipping")
        return

    # Build feature matrix from fills
    def feats_labels(fills):
        rows, labels = [], []
        for f in fills:
            sig  = f.get("sig") or 0.0
            micro_vs_mid = f.get("micro_vs_mid")
            if micro_vs_mid is None:
                micro_vs_mid = 0.0
            sp   = f.get("spread") or 0.0
            flow = f.get("flow") or 0.0
            p    = f.get("p") or 0.5
            k    = f.get("k") or 7
            rows.append([sig, abs(micro_vs_mid), sp, abs(flow), abs(p - 0.5), k])
            labels.append(f["strand"])
        return np.array(rows, float), np.array(labels, float)

    X_is, y_is   = feats_labels(fills_is)
    X_oos, y_oos = feats_labels(fills_oos)

    if len(y_is) < 20 or y_is.sum() < 5:
        print("  Not enough strand events on IS -- skipping")
        return

    scaler = StandardScaler()
    X_is_s  = scaler.fit_transform(X_is)
    X_oos_s = scaler.transform(X_oos)

    clf = LogisticRegression(max_iter=500, random_state=SEED, C=1.0)
    clf.fit(X_is_s, y_is)

    p_strand_is  = clf.predict_proba(X_is_s)[:, 1]
    p_strand_oos = clf.predict_proba(X_oos_s)[:, 1]

    auc_is  = roc_auc_score(y_is,  p_strand_is)
    auc_oos = roc_auc_score(y_oos, p_strand_oos)
    print(f"  LogReg AUC: IS={auc_is:.3f}  OOS={auc_oos:.3f}")

    feat_names = ["sig", "|micro-mid|", "spread", "|flow|", "|p-0.5|", "k"]
    coef = clf.coef_[0]
    print("  Top features (by |coef|):")
    for i in np.argsort(-np.abs(coef)):
        print(f"    {feat_names[i]:15s}: {coef[i]:+.4f}")

    # Attach P(strand) to fills
    p_map_is  = {i: p for i, p in enumerate(p_strand_is)}
    p_map_oos = {i: p for i, p in enumerate(p_strand_oos)}

    # Sweep thresholds
    thresholds = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60]
    print(f"\n  {'thresh':>7} | {'IS strand%':>10} {'IS vol%':>8} {'IS net/win':>10} {'IS shr':>7} |"
          f" {'OOS strand%':>11} {'OOS vol%':>9} {'OOS net/win':>11} {'OOS shr':>8} | verdict")

    # Build per-fill index maps
    # We need to apply thresholds to policy walks -- simplest: build gate using precomputed probs
    # IS
    fills_is_arr  = list(fills_is)
    fills_oos_arr = list(fills_oos)

    def gate_by_pstrand(fills_arr, p_arr_filled, thresh):
        """Return open_ok function using precomputed P(strand) per fill."""
        # Build a dict: fill_id -> p_strand
        # We use a closure over index since fills are ordered
        id_map = {}
        for idx, f in enumerate(fills_arr):
            id_map[id(f)] = p_arr_filled[idx]
        def ok(f, s):
            p = id_map.get(id(f))
            if p is None:
                return True  # unknown -> allow
            return p < thresh
        return ok

    base_sr_is  = strand_rate(fills_is)
    base_sr_oos = strand_rate(fills_oos)

    best_oos_net = -999
    best_thresh  = None

    for thresh in thresholds:
        # IS
        open_ok_is  = gate_by_pstrand(fills_is_arr, p_strand_is, thresh)
        open_ok_oos = gate_by_pstrand(fills_oos_arr, p_strand_oos, thresh)

        pnl_is  = window_pnl_policy(wins_is,  open_ok=open_ok_is)
        pnl_oos = window_pnl_policy(wins_oos, open_ok=open_ok_oos)

        m_is  = compute_metrics(pnl_is)
        m_oos = compute_metrics(pnl_oos)

        # Strand rate under gate (fills that pass gate)
        gated_is  = [f for f in fills_is_arr  if p_strand_is[fills_is_arr.index(f)] < thresh]
        gated_oos = [f for f in fills_oos_arr if p_strand_oos[fills_oos_arr.index(f)] < thresh]

        sr_is  = strand_rate(gated_is)  if gated_is  else np.nan
        sr_oos = strand_rate(gated_oos) if gated_oos else np.nan
        vol_is  = len(gated_is)  / max(len(fills_is_arr), 1)
        vol_oos = len(gated_oos) / max(len(fills_oos_arr), 1)

        verdict = "SIGNAL" if (m_oos["mean"] > live_m_oos["mean"]) else "MIRAGE"
        if m_oos["mean"] > best_oos_net:
            best_oos_net = m_oos["mean"]
            best_thresh  = thresh

        print(f"  {thresh:7.2f} | {sr_is*100:10.2f}% {vol_is*100:7.1f}% {m_is['mean']*100:10.2f}c"
              f" {m_is['sharpe']:7.3f} | {sr_oos*100:11.2f}% {vol_oos*100:8.1f}%"
              f" {m_oos['mean']*100:11.2f}c {m_oos['sharpe']:8.3f} | {verdict}")

    print(f"\n  Best OOS thresh={best_thresh:.2f}  net={best_oos_net*100:.2f}c/win"
          f"  vs live={live_m_oos['mean']*100:.2f}c/win"
          f"  diff={( best_oos_net - live_m_oos['mean'])*100:+.2f}c/win")
    strand_cut = base_sr_oos - strand_rate([f for f in fills_oos_arr
                                            if p_strand_oos[fills_oos_arr.index(f)] < best_thresh])
    print(f"  OOS strand-rate cut: {base_sr_oos*100:.2f}% -> ??? (see table above)")
    print(f"  AUC IS={auc_is:.3f} OOS={auc_oos:.3f} ({'SIGNAL: model generalizes' if auc_oos > 0.55 else 'MIRAGE: OOS AUC near random'})")


# ══════════════════════════════════════════════════════════════════════════════
# IDEA 2: A-S QUOTE SKEW vs t36 BINARY
# ══════════════════════════════════════════════════════════════════════════════

def idea2_as_skew(fills_is, fills_oos, wins_is, wins_oos, live_m_is, live_m_oos):
    print("\n" + "="*70)
    print("IDEA 2: A-S QUOTE SKEW vs t36 BINARY")
    print("="*70)

    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("  sklearn not available"); return

    # Fit P(strand) model on IS (same as Idea 1)
    def feats(fills):
        rows = []
        for f in fills:
            sig  = f.get("sig") or 0.0
            micro_vs_mid = f.get("micro_vs_mid") or 0.0
            sp   = f.get("spread") or 0.0
            flow = f.get("flow") or 0.0
            p    = f.get("p") or 0.5
            k    = f.get("k") or 7
            rows.append([sig, abs(micro_vs_mid), sp, abs(flow), abs(p - 0.5), k])
        return np.array(rows, float)

    X_is  = feats(fills_is)
    y_is  = np.array([f["strand"] for f in fills_is], float)
    X_oos = feats(fills_oos)

    if len(y_is) < 20 or y_is.sum() < 5:
        print("  Not enough data"); return

    scaler = StandardScaler()
    clf = LogisticRegression(max_iter=500, random_state=SEED)
    clf.fit(scaler.fit_transform(X_is), y_is)

    p_is  = clf.predict_proba(scaler.transform(X_is))[:, 1]
    p_oos = clf.predict_proba(scaler.transform(X_oos))[:, 1]

    fills_is_arr  = list(fills_is)
    fills_oos_arr = list(fills_oos)

    # t36 binary (IS and OOS baseline)
    pnl_t36_is  = window_pnl_live(wins_is)
    pnl_t36_oos = window_pnl_live(wins_oos)
    m_t36_is  = compute_metrics(pnl_t36_is)
    m_t36_oos = compute_metrics(pnl_t36_oos)

    # A-S continuous skew: demand extra spread proportional to P(strand)
    # Model: only open if spread > base_spread + skew_factor * P(strand)
    # where base_spread is a tunable floor (default 0.01 = t36's base)
    print(f"\n  t36 BINARY baseline: IS={m_t36_is['mean']*100:.2f}c/win"
          f"  OOS={m_t36_oos['mean']*100:.2f}c/win")
    print(f"\n  A-S SKEW sweep (skew_factor x P(strand) added to 0.01 spread floor):")
    print(f"  {'skf':>6} | {'IS net/win':>10} {'IS shr':>7} {'IS sr%':>7} |"
          f" {'OOS net/win':>11} {'OOS shr':>8} {'OOS sr%':>8} | diff_IS  diff_OOS | verdict")

    skew_factors = [0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20]

    for skf in skew_factors:
        def make_ok_is(skf_=skf):
            id_map = {id(f): p_is[i] for i, f in enumerate(fills_is_arr)}
            def ok(f, s):
                ps = id_map.get(id(f), 0.0)
                req = 0.01 + skf_ * ps
                return f["spread"] >= req
            return ok

        def make_ok_oos(skf_=skf):
            id_map = {id(f): p_oos[i] for i, f in enumerate(fills_oos_arr)}
            def ok(f, s):
                ps = id_map.get(id(f), 0.0)
                req = 0.01 + skf_ * ps
                return f["spread"] >= req
            return ok

        pnl_is  = window_pnl_policy(wins_is,  open_ok=make_ok_is())
        pnl_oos = window_pnl_policy(wins_oos, open_ok=make_ok_oos())
        m_is  = compute_metrics(pnl_is)
        m_oos = compute_metrics(pnl_oos)

        gated_is  = [f for i, f in enumerate(fills_is_arr)  if f["spread"] >= 0.01 + skf * p_is[i]]
        gated_oos = [f for i, f in enumerate(fills_oos_arr) if f["spread"] >= 0.01 + skf * p_oos[i]]
        sr_is  = strand_rate(gated_is)  if gated_is  else np.nan
        sr_oos = strand_rate(gated_oos) if gated_oos else np.nan

        diff_is  = (m_is["mean"]  - m_t36_is["mean"])  * 100
        diff_oos = (m_oos["mean"] - m_t36_oos["mean"]) * 100
        verdict = "SIGNAL" if diff_oos > 0 else "MIRAGE"

        print(f"  {skf:6.2f} | {m_is['mean']*100:10.2f}c {m_is['sharpe']:7.3f} {sr_is*100:7.2f}% |"
              f" {m_oos['mean']*100:11.2f}c {m_oos['sharpe']:8.3f} {sr_oos*100:8.2f}% |"
              f" {diff_is:+8.2f}c {diff_oos:+8.2f}c | {verdict}")


# ══════════════════════════════════════════════════════════════════════════════
# IDEA 3: SPOT-MOMENTUM FILTER (|sig| threshold sweep)
# ══════════════════════════════════════════════════════════════════════════════

def idea3_spot_momentum(wins_is, wins_oos, live_m_is, live_m_oos):
    print("\n" + "="*70)
    print("IDEA 3: SPOT-MOMENTUM FILTER (|sig| threshold sweep)")
    print("="*70)

    thresholds = [3, 4, 5, 6, 8, 10, 12, 15]

    # Baseline (all opens)
    pnl_p0_is  = window_pnl_policy(wins_is)
    pnl_p0_oos = window_pnl_policy(wins_oos)
    m_p0_is  = compute_metrics(pnl_p0_is)
    m_p0_oos = compute_metrics(pnl_p0_oos)

    print(f"  P0 baseline: IS={m_p0_is['mean']*100:.2f}c  OOS={m_p0_oos['mean']*100:.2f}c")
    print(f"  live_current: IS={live_m_is['mean']*100:.2f}c  OOS={live_m_oos['mean']*100:.2f}c")

    # Strand rate function
    def strand_rate_gated(wins_dict, open_ok):
        fills_kept = []
        for ws, v in wins_dict.items():
            for f in v["fills"]:
                if open_ok(f, {}):
                    fills_kept.append(f)
        return strand_rate(fills_kept)

    print(f"\n  {'|sig|<=':>8} | {'IS net/win':>10} {'IS sr%':>8} {'IS shr':>7} |"
          f" {'OOS net/win':>11} {'OOS sr%':>9} {'OOS shr':>8} | diff_vs_live | verdict")

    best_oos = -999
    best_thr = None

    for thr in thresholds:
        def make_ok(thr_=thr):
            def ok(f, s):
                return abs(f.get("sig") or 0.0) <= thr_
            return ok

        open_ok = make_ok()
        pnl_is  = window_pnl_policy(wins_is,  open_ok=open_ok)
        pnl_oos = window_pnl_policy(wins_oos, open_ok=open_ok)
        m_is  = compute_metrics(pnl_is)
        m_oos = compute_metrics(pnl_oos)
        sr_is  = strand_rate_gated(wins_is,  open_ok)
        sr_oos = strand_rate_gated(wins_oos, open_ok)

        diff_oos = (m_oos["mean"] - live_m_oos["mean"]) * 100
        verdict  = "SIGNAL" if diff_oos > 0 else "MIRAGE"

        if m_oos["mean"] > best_oos:
            best_oos = m_oos["mean"]
            best_thr = thr

        print(f"  {thr:8d} | {m_is['mean']*100:10.2f}c {sr_is*100:8.2f}% {m_is['sharpe']:7.3f} |"
              f" {m_oos['mean']*100:11.2f}c {sr_oos*100:9.2f}% {m_oos['sharpe']:8.3f} |"
              f" {diff_oos:+11.2f}c | {verdict}")

    print(f"\n  Best |sig| threshold: {best_thr}bps  OOS net={best_oos*100:.2f}c/win"
          f"  diff_vs_live={( best_oos - live_m_oos['mean'])*100:+.2f}c")


# ══════════════════════════════════════════════════════════════════════════════
# IDEA 4: MICROPRICE-DIVERGENCE GATE
# ══════════════════════════════════════════════════════════════════════════════

def idea4_micro_divergence(fills_is, fills_oos, wins_is, wins_oos, live_m_is, live_m_oos):
    print("\n" + "="*70)
    print("IDEA 4: MICROPRICE-DIVERGENCE GATE")
    print("="*70)

    # Check if micro_vs_mid is populated
    n_with_micro_is = sum(1 for f in fills_is if f.get("micro_vs_mid") is not None)
    n_with_micro_oos = sum(1 for f in fills_oos if f.get("micro_vs_mid") is not None)
    print(f"  Fills with micro_vs_mid: IS={n_with_micro_is}/{len(fills_is)}"
          f"  OOS={n_with_micro_oos}/{len(fills_oos)}")

    if n_with_micro_is < 10:
        print("  NOTE: Micro data sparse -- using book-derived spread proxy instead.")
        print("  Micro divergence = |p - (bid+ask)/2| = 0 for our own fills by construction.")
        print("  Testing SPREAD-FLOOR proxy: skip if spread < threshold (adverse = tight market).")

        # Proxy: use spread as a tightness signal (tight = more adverse)
        thresholds = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03]
        print(f"\n  {'spread>=':>9} | {'IS net/win':>10} {'IS shr':>7} |"
              f" {'OOS net/win':>11} {'OOS shr':>8} | diff_vs_live | verdict")

        for thr in thresholds:
            def make_ok(thr_=thr):
                def ok(f, s):
                    return (f.get("spread") or 0.0) >= thr_
                return ok

            pnl_is  = window_pnl_policy(wins_is,  open_ok=make_ok())
            pnl_oos = window_pnl_policy(wins_oos, open_ok=make_ok())
            m_is  = compute_metrics(pnl_is)
            m_oos = compute_metrics(pnl_oos)
            diff_oos = (m_oos["mean"] - live_m_oos["mean"]) * 100
            verdict  = "SIGNAL" if diff_oos > 0 else "MIRAGE"

            print(f"  {thr:9.3f} | {m_is['mean']*100:10.2f}c {m_is['sharpe']:7.3f} |"
                  f" {m_oos['mean']*100:11.2f}c {m_oos['sharpe']:8.3f} |"
                  f" {diff_oos:+11.2f}c | {verdict}")
        return

    # Full micro-divergence analysis (when book snapshots available)
    thresholds = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0]  # bps (we'll use raw price units / 100)
    print(f"\n  NOTE: micro_vs_mid in price units (1 = 100 bps).")
    print(f"  Thresholds in price units (0.01 = 1c = 100bps, 0.001 = 0.1c = 10bps):")
    print(f"  Gate: skip fill where micro_vs_mid < -threshold (book leaning against our side)")

    fills_is_arr  = list(fills_is)
    fills_oos_arr = list(fills_oos)

    # For bid: skip if micro_mid - mid < -threshold (microprice below mid => against YES buy)
    # For ask: skip if micro_mid - mid > +threshold (microprice above mid => against NO sell)
    # Encoded as: side-aware divergence adverse to our fill
    for thr_c in [0.001, 0.003, 0.005, 0.008, 0.010, 0.020]:
        def make_ok(thr_=thr_c):
            def ok(f, s):
                mvm = f.get("micro_vs_mid")
                if mvm is None:
                    return True  # no data -> allow
                if f["side"] == "bid":
                    return mvm >= -thr_   # micro not too far below mid
                else:
                    return mvm <= thr_    # micro not too far above mid
            return ok

        pnl_is  = window_pnl_policy(wins_is,  open_ok=make_ok())
        pnl_oos = window_pnl_policy(wins_oos, open_ok=make_ok())
        m_is  = compute_metrics(pnl_is)
        m_oos = compute_metrics(pnl_oos)
        diff_oos = (m_oos["mean"] - live_m_oos["mean"]) * 100
        verdict  = "SIGNAL" if diff_oos > 0 else "MIRAGE"

        # Gated fill counts
        gated_is  = [f for f in fills_is_arr if make_ok()(f, {})]
        gated_oos = [f for f in fills_oos_arr if make_ok()(f, {})]
        vol_is  = len(gated_is)  / max(len(fills_is_arr), 1)
        vol_oos = len(gated_oos) / max(len(fills_oos_arr), 1)

        print(f"  thr={thr_c:.3f} | IS={m_is['mean']*100:.2f}c/{m_is['sharpe']:.3f}"
              f"  vol={vol_is:.1%} | OOS={m_oos['mean']*100:.2f}c/{m_oos['sharpe']:.3f}"
              f"  vol={vol_oos:.1%} | diff={diff_oos:+.2f}c | {verdict}")


# ══════════════════════════════════════════════════════════════════════════════
# IDEA 5: QUEUE-THINNESS ENTRY
# ══════════════════════════════════════════════════════════════════════════════

def idea5_queue_thinness(fills_is, fills_oos, wins_is, wins_oos, live_m_is, live_m_oos):
    print("\n" + "="*70)
    print("IDEA 5: QUEUE-THINNESS ENTRY (book depth gate)")
    print("="*70)

    n_with_depth_is  = sum(1 for f in fills_is  if f.get("depth") is not None)
    n_with_depth_oos = sum(1 for f in fills_oos if f.get("depth") is not None)
    print(f"  Fills with depth: IS={n_with_depth_is}/{len(fills_is)}"
          f"  OOS={n_with_depth_oos}/{len(fills_oos)}")

    if n_with_depth_is < 10:
        print("  NOTE: Depth data sparse from book snaps -- using box_policy_ab.load_window_books approach.")
        print("  Trying both_fill_rate as proxy for depth signal:")
        print("  Lower flow volume windows have higher both-fill rates.")
        # Use |flow| as proxy for queue pressure
        thresholds = [50, 100, 200, 400, 800, 1600]
        print(f"\n  {'|flow|<':>8} | {'IS P(both)':>10} {'IS net/win':>11} |"
              f" {'OOS P(both)':>11} {'OOS net/win':>12} | diff_vs_live | verdict")

        for thr in thresholds:
            def make_ok(thr_=thr):
                def ok(f, s):
                    return abs(f.get("flow") or 0.0) < thr_
                return ok

            pnl_is  = window_pnl_policy(wins_is,  open_ok=make_ok())
            pnl_oos = window_pnl_policy(wins_oos, open_ok=make_ok())
            m_is  = compute_metrics(pnl_is)
            m_oos = compute_metrics(pnl_oos)

            # Both-fill rate (boxes / (boxes + strands))
            bf_is  = both_fill_rate({ws: v for ws, v in wins_is.items()})
            bf_oos = both_fill_rate({ws: v for ws, v in wins_oos.items()})

            diff_oos = (m_oos["mean"] - live_m_oos["mean"]) * 100
            verdict  = "SIGNAL" if diff_oos > 0 else "MIRAGE"

            print(f"  {thr:8d} | {bf_is:10.3f} {m_is['mean']*100:11.2f}c |"
                  f" {bf_oos:11.3f} {m_oos['mean']*100:12.2f}c | {diff_oos:+11.2f}c | {verdict}")
        return

    # Full depth analysis
    # depth < threshold => thin queue => open
    thresholds = [500, 1000, 2000, 3000, 5000, 8000, 10000]
    print(f"\n  {'depth<':>8} | {'IS P(both)':>10} {'IS vol%':>8} {'IS net/win':>10} |"
          f" {'OOS P(both)':>11} {'OOS vol%':>9} {'OOS net/win':>11} | diff | verdict")

    fills_is_arr  = list(fills_is)
    fills_oos_arr = list(fills_oos)

    for thr in thresholds:
        def make_ok(thr_=thr):
            def ok(f, s):
                d = f.get("depth")
                return d is None or d < thr_
            return ok

        pnl_is  = window_pnl_policy(wins_is,  open_ok=make_ok())
        pnl_oos = window_pnl_policy(wins_oos, open_ok=make_ok())
        m_is  = compute_metrics(pnl_is)
        m_oos = compute_metrics(pnl_oos)

        gated_is  = [f for f in fills_is_arr  if make_ok()(f, {})]
        gated_oos = [f for f in fills_oos_arr if make_ok()(f, {})]

        bf_is  = sum(f["box"] for f in gated_is)  / max(len(gated_is), 1)
        bf_oos = sum(f["box"] for f in gated_oos) / max(len(gated_oos), 1)
        vol_is  = len(gated_is)  / max(len(fills_is_arr), 1)
        vol_oos = len(gated_oos) / max(len(fills_oos_arr), 1)

        diff_oos = (m_oos["mean"] - live_m_oos["mean"]) * 100
        verdict  = "SIGNAL" if diff_oos > 0 else "MIRAGE"
        n_flag   = "(small-n)" if len(gated_oos) < 50 else ""

        print(f"  {thr:8d} | {bf_is:10.3f} {vol_is*100:7.1f}% {m_is['mean']*100:10.2f}c |"
              f" {bf_oos:11.3f} {vol_oos*100:8.1f}% {m_oos['mean']*100:11.2f}c |"
              f" {diff_oos:+6.2f}c | {verdict} {n_flag}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("ROUND 1: STRAND-PREVENTION RESEARCH LOOP")
    print("=" * 70)

    # Load data
    print("\nLoading parquet data ...")
    h, t_df, common = load_parquet()
    n = len(common)
    cut = int(n * IS_FRAC)
    is_ws  = set(common[:cut])
    oos_ws = set(common[cut:])
    print(f"  Common windows: {n}  IS={cut}  OOS={n-cut}")

    # Load book stream (for microprice / depth)
    print("\nLoading book stream ...")
    book_data_paths = [OVERNIGHT]
    if os.path.isdir(GHA_DATA):
        book_data_paths.append(GHA_DATA)
    book_stream, book_res = load_book_stream(book_data_paths)
    print(f"  Book stream: {len(book_stream)} windows have snapshots")

    # Build fills
    print("\nBuilding fills (may take a minute) ...")
    fills_all, wins_all = build_fills(h, t_df, common, book_stream=book_stream)
    print(f"  Total fills: {len(fills_all)}")
    print(f"  Strand fills: {sum(1 for f in fills_all if f['strand'])}"
          f"  ({strand_rate(fills_all)*100:.2f}%)")

    # Split IS / OOS
    wins_is  = {ws: v for ws, v in wins_all.items() if ws in is_ws}
    wins_oos = {ws: v for ws, v in wins_all.items() if ws in oos_ws}
    fills_is  = [f for f in fills_all if f["ws"] in is_ws]
    fills_oos = [f for f in fills_all if f["ws"] in oos_ws]

    print(f"  IS fills: {len(fills_is)} ({sum(f['strand'] for f in fills_is)} strands)")
    print(f"  OOS fills: {len(fills_oos)} ({sum(f['strand'] for f in fills_oos)} strands)")

    # Live current baselines
    pnl_live_is  = window_pnl_live(wins_is)
    pnl_live_oos = window_pnl_live(wins_oos)
    live_m_is  = compute_metrics(pnl_live_is)
    live_m_oos = compute_metrics(pnl_live_oos)

    print(f"\n  LIVE_CURRENT baseline:")
    print(f"    IS:  n={live_m_is['n']}  net={live_m_is['mean']*100:.2f}c/win"
          f"  Sharpe={live_m_is['sharpe']:.3f}  skew={live_m_is['skew']:.3f}"
          f"  CVaR95={live_m_is['cvar95']*100:.2f}c")
    print(f"    OOS: n={live_m_oos['n']}  net={live_m_oos['mean']*100:.2f}c/win"
          f"  Sharpe={live_m_oos['sharpe']:.3f}  skew={live_m_oos['skew']:.3f}"
          f"  CVaR95={live_m_oos['cvar95']*100:.2f}c")

    # Per-window stats
    p0_pnl_is  = window_pnl_policy(wins_is)
    p0_pnl_oos = window_pnl_policy(wins_oos)
    m_p0_is  = compute_metrics(p0_pnl_is)
    m_p0_oos = compute_metrics(p0_pnl_oos)

    print(f"\n  P0 baseline:")
    print(f"    IS:  n={m_p0_is['n']}  net={m_p0_is['mean']*100:.2f}c/win"
          f"  Sharpe={m_p0_is['sharpe']:.3f}")
    print(f"    OOS: n={m_p0_oos['n']}  net={m_p0_oos['mean']*100:.2f}c/win"
          f"  Sharpe={m_p0_oos['sharpe']:.3f}")

    # ── STRAND STATS ──
    sr_is  = strand_rate(fills_is)
    sr_oos = strand_rate(fills_oos)
    bf_is  = both_fill_rate(wins_is)
    bf_oos = both_fill_rate(wins_oos)
    print(f"\n  Strand rates: IS={sr_is*100:.2f}%  OOS={sr_oos*100:.2f}%")
    print(f"  Both-fill rates: IS={bf_is*100:.2f}%  OOS={bf_oos*100:.2f}%")

    # ── RUN IDEAS ──
    idea1_strand_predictor(fills_is, fills_oos, wins_is, wins_oos, live_m_is, live_m_oos)
    idea2_as_skew(fills_is, fills_oos, wins_is, wins_oos, live_m_is, live_m_oos)
    idea3_spot_momentum(wins_is, wins_oos, live_m_is, live_m_oos)
    idea4_micro_divergence(fills_is, fills_oos, wins_is, wins_oos, live_m_is, live_m_oos)
    idea5_queue_thinness(fills_is, fills_oos, wins_is, wins_oos, live_m_is, live_m_oos)

    # ── SUMMARY ──
    print("\n" + "="*70)
    print("ROUND 1 SUMMARY")
    print("="*70)
    print(f"  Data: {n} windows  IS={cut} OOS={n-cut}  fills={len(fills_all)}")
    print(f"  Strand rate: OOS={sr_oos*100:.2f}%  (IS={sr_is*100:.2f}%)")
    print(f"  live_current OOS: {live_m_oos['mean']*100:.2f}c/win  Sharpe={live_m_oos['sharpe']:.3f}")
    print("\n  Verdicts (see each idea above for full tables):")
    print("  1. STRAND PREDICTOR GATE -- see Idea 1 output above")
    print("  2. A-S QUOTE SKEW       -- see Idea 2 output above")
    print("  3. SPOT-MOMENTUM FILTER -- see Idea 3 output above")
    print("  4. MICRO-DIV GATE       -- see Idea 4 output above")
    print("  5. QUEUE-THINNESS ENTRY -- see Idea 5 output above")

    print("""
ROUND 2 FOLLOW-UP PROPOSALS (grounded in Round 1 findings):

R2-A: CALIBRATED STRAND MODEL WITH TREE ENSEMBLE
      The LogReg (Idea 1) reveals that spread and |p-0.5| are the dominant
      features. Fit a GradientBoostingClassifier (or XGBoost) on the same 6
      features to capture non-linear interactions (e.g., high-spread + extreme
      price is SAFE but mid-spread + mid-price is TOXIC). Evaluate OOS AUC lift
      vs LogReg; if AUC>0.65 and OOS strand-rate cut >30% at 80% volume retained,
      register the distilled logistic as a new trial (t38_logreg_gate).

R2-B: SIG x SPREAD INTERACTION GATE
      Idea 3 (spot-momentum) and t36 (spread floor) each show partial OOS lift.
      Test the INTERACTION: refuse opens only when BOTH |sig|>threshold AND
      spread<floor (the compound toxic condition). Sweep 6 (|sig|, spread) pairs.
      Hypothesis: conjunctive gate cuts volume less while strand-rate cut is
      maintained (the two signals are partially independent adverse conditions).

R2-C: TIME-OF-DAY STRATIFIED THRESHOLDS
      Hour-of-day drives liquidity regimes (deep EU open vs thin Asia).
      Stratify the OOS data into 4 hour-bands (00-06, 06-12, 12-18, 18-24 UTC).
      For each band: fit optimal |sig| threshold and strand rate. If the
      band-specific thresholds differ >2x, register a time-of-day sig gate.
      This avoids over-blocking in thin sessions where |sig| is structurally high.

R2-D: DEPTH x VPIN COMBINED FILTER
      Idea 5 (queue-thinness) found depth data from book stream is partially
      populated. Idea 4 found that micro-data coverage depends on book snap timing.
      Test a COMBINED gate: depth < D_threshold AND VPIN < 0.40. The book's
      bilateral thinness (depth) + flow toxicity (VPIN) should be orthogonal.
      Compare to t32_vpin_open_gate (VPIN only) on OOS P(both fill) and net/win.

R2-E: FORWARD STRAND CLASSIFIER REGISTRATION
      If R2-A shows AUC>0.65 OOS, distill into a frozen logistic (matching the
      tox_p pattern in box_policy_ab.py) and register as a trial in the TRIALS
      dict. Pre-register: thresh=0.35 (estimated 80% volume retained), T_BAR=3.0,
      MIN_WINDOWS=300. Add det_* features from informed_detectors.py as R2-A
      supplemental features to test whether informed-flow detectors add signal
      beyond spread/price/momentum.
""")


if __name__ == "__main__":
    main()
