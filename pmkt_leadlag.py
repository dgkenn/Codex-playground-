"""pmkt_leadlag.py -- Polymarket -> Kalshi lead-lag analysis harness.

WHY: We maker-box Kalshi KXBTC15M (15-min BTC binary) and suspect Polymarket's
deeper 5-min BTC up/down book incorporates BTC information faster.  If Polymarket
LEADS Kalshi beyond what BTC spot already tells us, that lead-time is a fair-value
signal we can embed in quote logic to reduce adverse selection on unpaired legs.
The decisive test is incremental: does the Polymarket term survive a regression that
already includes spot changes?  If not, there is nothing actionable.

    python pmkt_leadlag.py [--dirs d1 d2 ...] [--asset btc] [--grid 2]
    python pmkt_leadlag.py --synthetic          # self-test, no real data needed

Kalshi book ticks are loaded by reusing box_policy_ab.iter_gz (not re-written).
Polymarket rows come from pmkt_btc_updown_*.jsonl.gz (written by pmkt_collect.py).
BTC spot comes from the 'spot' field embedded in each Kalshi book tick.

HAC/Newey-West t-stats are computed manually (no statsmodels):
  sandwich = (X'X)^-1 * S * (X'X)^-1,  S = Bartlett-weighted cross-lag scores.

Regression model (all in change / increment space):
  y[t]  = Sigma ΔKalshi over [t, t+W)         (future W-second mid change)
  xp[t] = Sigma ΔPoly   over [t-W, t)         (past W-second Poly change)
  xs[t] = Sigma ΔSpot   over [t-W, t)         (past W-second spot, control)
  Fit y ~ const + b_poly*xp + b_spot*xs with HAC se.
  b_poly significant WITH spot present = Poly leads Kalshi BEYOND spot.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
from typing import List, Tuple

import numpy as np
import pandas as pd

DEFAULT_DIRS   = ["overnight_data", "gha_data"]
GRID_S         = 2      # resample grid in seconds
MAX_GAP_S      = 10     # NaN-out stale forward-fills longer than this
MAXLAG_S       = 30     # cross-corr range
PRED_WINDOW_S  = 5      # regression prediction horizon
NW_LAGS        = 5      # Newey-West bandwidth


# ── helpers ────────────────────────────────────────────────────────────────

def _iter_gz(fp):
    """Yield JSON records from a gzip-JSONL file; tolerates truncated tail."""
    try:
        with gzip.open(fp, "rt") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except Exception:
                    continue
    except (EOFError, OSError, gzip.BadGzipFile):
        return


def _import_iter_gz():
    """Prefer box_policy_ab.iter_gz (identical logic, single source of truth)."""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "_bpa", os.path.join(here, "box_policy_ab.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.iter_gz


def _rs(arr: np.ndarray, w: int) -> np.ndarray:
    """Rolling window sum: rs[i] = arr[i] + ... + arr[i+w-1].  len = len(arr)-w+1."""
    cs = np.concatenate([[0.0], np.cumsum(arr)])
    return cs[w:] - cs[:-w]


# ── data loaders ───────────────────────────────────────────────────────────

def load_kalshi_ticks(dirs: List[str], asset: str = "btc"):
    """Return sorted (t, yes_mid, spot) arrays from all Kalshi book files."""
    try:
        igz = _import_iter_gz()
    except Exception:
        igz = _iter_gz

    rows: List[Tuple[float, float, float]] = []
    for d in dirs:
        seen: set = set()
        for pat in [os.path.join(d, "**", f"book_kalshi_{asset}15m_*.jsonl.gz"),
                    os.path.join(d, f"book_kalshi_{asset}15m_*.jsonl.gz")]:
            for fp in glob.glob(pat, recursive=True):
                if fp in seen:
                    continue
                seen.add(fp)
                for r in igz(fp):
                    if r.get("type") != "book":
                        continue
                    yb = r.get("yes") or []
                    nb = r.get("no") or []
                    if not yb or not nb:
                        continue
                    yes_bid = float(yb[-1][0])
                    yes_ask = round(1.0 - float(nb[-1][0]), 4)
                    yes_mid = (yes_bid + yes_ask) / 2.0
                    sp = r.get("spot")
                    if sp is None:
                        continue
                    rows.append((float(r["t"]), yes_mid, float(sp)))
    if not rows:
        return np.array([]), np.array([]), np.array([])
    rows.sort()
    t, mid, spot = zip(*rows)
    return np.array(t), np.array(mid), np.array(spot)


def load_pmkt_ticks(dirs: List[str], asset: str = "btc"):
    """Return sorted (t, up_mid) arrays + list of searched globs."""
    rows: List[Tuple[float, float]] = []
    searched: List[str] = []
    for d in dirs:
        for pat in [os.path.join(d, "**", f"pmkt_{asset}_updown_*.jsonl.gz"),
                    os.path.join(d, f"pmkt_{asset}_updown_*.jsonl.gz")]:
            searched.append(pat)
            for fp in glob.glob(pat, recursive=True):
                try:
                    with gzip.open(fp, "rt") as fh:
                        for ln in fh:
                            try:
                                r = json.loads(ln)
                            except Exception:
                                continue
                            ub, ua = r.get("up_bid"), r.get("up_ask")
                            if ub is None or ua is None:
                                continue
                            rows.append((float(r["t"]), (float(ub) + float(ua)) / 2.0))
                except (EOFError, OSError, gzip.BadGzipFile):
                    pass
    if not rows:
        return np.array([]), np.array([]), searched
    rows.sort()
    t, mid = zip(*rows)
    return np.array(t), np.array(mid), searched


# ── alignment ──────────────────────────────────────────────────────────────

def align_series(t_k, mid_k, t_p, mid_p, t_s, spot,
                 grid_s=GRID_S, max_gap_s=MAX_GAP_S) -> pd.DataFrame:
    """Resample all three to a common uniform grid; NaN where gap > max_gap_s."""
    if len(t_k) == 0:
        return pd.DataFrame()
    t_min = max(t_k.min(), t_p.min() if len(t_p) else t_k.min())
    t_max = min(t_k.max(), t_p.max() if len(t_p) else t_k.max())
    if t_min >= t_max:
        return pd.DataFrame()

    grid = np.arange(t_min, t_max, grid_s)
    idx  = pd.to_datetime(grid, unit="s", utc=True)

    def _resamp(ts, vals):
        if len(ts) == 0:
            return pd.Series(np.nan, index=idx)
        raw = pd.Series(vals, index=pd.to_datetime(ts, unit="s", utc=True))
        raw = raw[~raw.index.duplicated(keep="last")].reindex(idx, method="ffill")
        tt  = pd.Series(ts, index=pd.to_datetime(ts, unit="s", utc=True))
        tt  = tt[~tt.index.duplicated(keep="last")].reindex(idx, method="ffill")
        raw[(grid - tt.values) > max_gap_s] = np.nan
        return raw

    return pd.DataFrame({
        "kalshi": _resamp(t_k, mid_k),
        "pmkt":   _resamp(t_p, mid_p) if len(t_p) else np.nan,
        "spot":   _resamp(t_s, spot),
    }, index=idx)


# ── statistics ─────────────────────────────────────────────────────────────

def cross_corr(x: np.ndarray, y: np.ndarray, max_lag: int):
    """corr(x_t, y_{t+k}) for k in [-max_lag, +max_lag]."""
    n     = len(x)
    lags  = np.arange(-max_lag, max_lag + 1)
    corrs = np.full(len(lags), np.nan)
    if x.std() == 0 or y.std() == 0:
        return lags, corrs
    for i, k in enumerate(lags):
        a, b = (x[:n - k], y[k:]) if k >= 0 else (x[-k:], y[:n + k])
        if len(a) >= 30:
            corrs[i] = float(np.corrcoef(a, b)[0, 1])
    return lags, corrs


def newey_west_tstat(y: np.ndarray, X: np.ndarray, nw_lags: int = NW_LAGS):
    """OLS + Newey-West HAC t-statistics (vectorised, O(n*lags*k^2) matmul)."""
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    e     = y - X @ beta
    XtXi  = np.linalg.pinv(X.T @ X)
    score = e[:, None] * X          # (n, k) -- score[t] = e[t] * X[t,:]
    S     = score.T @ score         # lag-0 outer-product sum
    for lag in range(1, nw_lags + 1):
        w = 1.0 - lag / (nw_lags + 1.0)          # Bartlett weight
        cross = score[lag:].T @ score[:-lag]
        S    += w * (cross + cross.T)
    V  = XtXi @ S @ XtXi
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    return beta, np.where(se > 0, beta / se, 0.0)


# ── main analysis ──────────────────────────────────────────────────────────

def run_analysis(dirs, asset="btc", grid_s=GRID_S):
    t_k, mid_k, spot_k     = load_kalshi_ticks(dirs, asset)
    t_p, mid_p, searched   = load_pmkt_ticks(dirs, asset)

    if len(t_p) == 0:
        print("=" * 60)
        print("NO POLYMARKET DATA YET -- rerun after collection accumulates.")
        print("Searched globs:")
        for s in searched:
            print(f"  {s}")
        print("=" * 60)
        if len(t_k) > 0:
            print(f"Kalshi data: {(t_k.max()-t_k.min())/3600:.1f}h, {len(t_k)} ticks")
        return

    df = align_series(t_k, mid_k, t_p, mid_p, spot_k, spot_k, grid_s=grid_s)
    if df.empty or df.dropna().shape[0] < 100:
        print("Insufficient overlapping data after alignment (need >=100 rows).")
        return

    n_full = df.dropna().shape[0]
    print("=" * 60)
    print("DATA COVERAGE")
    print(f"  Aligned span : {len(df)*grid_s/3600:.2f}h  "
          f"({len(df)} grid pts @ {grid_s}s)")
    print(f"  Full (no gap): {n_full}  |  Gap rows: {df.isna().any(axis=1).sum()}")
    print(f"  Kalshi ticks : {len(t_k)}  |  Pmkt ticks: {len(t_p)}")

    clean = df.dropna()
    step  = max(1, PRED_WINDOW_S // grid_s)
    N     = len(clean)
    dk    = clean["kalshi"].diff().fillna(0).values
    dp    = clean["pmkt"].diff().fillna(0).values
    ds    = clean["spot"].diff().fillna(0).values

    # ── cross-correlation ──
    mls = MAXLAG_S // grid_s
    lags_p, corrs_p = cross_corr(dp, dk, mls)
    lags_s, corrs_s = cross_corr(ds, dk, mls)

    def _peak(lags, corrs):
        v = ~np.isnan(corrs)
        if not v.any():
            return 0, 0.0
        i = np.argmax(np.abs(corrs[v]))
        return int(lags[v][i]) * grid_s, float(corrs[v][i])

    pk_lp, pk_cp = _peak(lags_p, corrs_p)
    pk_ls, pk_cs = _peak(lags_s, corrs_s)

    print()
    print("CROSS-CORRELATION  (lag>0 => venue leads Kalshi)")
    print(f"  {'Source':<8} {'Peak lag(s)':>11} {'Peak corr':>10}  Note")
    print(f"  Pmkt     {pk_lp:>+11}  {pk_cp:>+10.3f}  "
          f"{'Poly LEADS' if pk_lp>0 else 'no/contemporaneous lead'}")
    print(f"  Spot     {pk_ls:>+11}  {pk_cs:>+10.3f}  "
          f"{'Spot LEADS' if pk_ls>0 else 'no spot lead'}")
    print()
    print("  Poly->Kalshi cross-corr top-5 by |corr|:")
    vm    = ~np.isnan(corrs_p)
    order = np.argsort(-np.abs(corrs_p[vm]))[:5]
    for i in order:
        print(f"    lag={int(lags_p[vm][i])*grid_s:+4d}s  corr={corrs_p[vm][i]:+.4f}")

    # ── regression ──
    # y[t]  = rs(dk,step)[t]              (future Kalshi change from t)
    # xp[t] = rs(dp,step)[t-step]         (past Poly change ending at t)
    # xs[t] = rs(ds,step)[t-step]         (past spot change, control)
    dk_fwd  = _rs(dk, step)
    dp_past = _rs(dp, step)
    ds_past = _rs(ds, step)
    i0, i1  = step, N - step
    y_r  = dk_fwd[i0:i1]
    dp_r = dp_past[i0 - step: i1 - step]
    ds_r = ds_past[i0 - step: i1 - step]

    ok  = np.all(np.isfinite(np.column_stack([y_r, dp_r, ds_r])), axis=1)
    y_r, dp_r, ds_r = y_r[ok], dp_r[ok], ds_r[ok]
    if len(y_r) < 30:
        print("Not enough rows for regression.")
        return
    Xr = np.column_stack([np.ones(len(y_r)), dp_r, ds_r])
    beta, tstats = newey_west_tstat(y_r, Xr, nw_lags=NW_LAGS)

    print()
    print(f"INCREMENTAL REGRESSION  (W={PRED_WINDOW_S}s, HAC NW-lags={NW_LAGS})")
    print(f"  ΔKalshi_fwd ~ const + b_poly·ΔPoly_past + b_spot·ΔSpot_past  (n={len(y_r)})")
    print(f"  {'Term':<12} {'β':>10} {'NW t-stat':>10}  Sig?")
    for nm, b, t in zip(["const", "Δpoly", "Δspot"], beta, tstats):
        s = "***" if abs(t)>3 else ("**" if abs(t)>2 else ("*" if abs(t)>1.65 else ""))
        print(f"  {nm:<12} {b:>+10.5f} {t:>+10.2f}  {s}")

    poly_t = tstats[1]
    print()
    print("VERDICT")
    if abs(poly_t) >= 2.0:
        d = "LEADS" if poly_t > 0 else "INVERSELY LEADS"
        tdp = (np.percentile(np.abs(dp_r[dp_r!=0]), 75)
               if (dp_r!=0).any() else 0.0)
        print(f"  ACTIONABLE: Poly {d} Kalshi (t={poly_t:+.2f} >= 2.0).")
        print(f"  Implied edge ~ {abs(beta[1]*tdp)*100:.3f}c per quote-adjustment.")
    else:
        print(f"  NOT SIGNIFICANT (t={poly_t:+.2f}). Poly adds no incremental info.")
        print("  Recommendation: do NOT add Polymarket-based quote adjustments.")
    print("=" * 60)


# ── synthetic self-test ────────────────────────────────────────────────────

def run_synthetic():
    """Verify the harness: Scenario A -> insignificant, Scenario B -> significant.

    DGP (increment space, all N(0,1) innovations):
      dspot[t]   -- common BTC factor seen by both venues
      priv[t]    -- Poly-only informed flow (Kalshi cannot see it directly)

    Scenario A: dp = 0.5*dspot + 0.5*noise;  dk = 0.5*dspot + 0.5*noise
      (Poly has no private signal; both are pure spot followers)

    Scenario B: dp = 0.5*dspot + 0.5*priv;  dk = 0.5*dspot + 0.5*noise + 0.4*priv[t-step]
      (Poly embeds priv; Kalshi absorbs it with a one-step = 5s lag)

    Regression xp = rs(dp, step)[t-step] extracts the private signal from dp_past
    after controlling for xs = rs(dspot, step)[t-step].  It should be significant
    only in B.
    """
    rng   = np.random.default_rng(42)
    n     = 3600
    step  = PRED_WINDOW_S // GRID_S   # 5s / 2s = 2

    print()
    for label, poly_lead in [("A (no Poly lead)", False), ("B (Poly leads 5s)", True)]:
        dspot = rng.normal(0, 1.0, n)
        priv  = rng.normal(0, 1.0, n)
        noisep = rng.normal(0, 1.0, n)
        noisek = rng.normal(0, 1.0, n)

        dp = 0.5 * dspot + 0.5 * (priv if poly_lead else noisep)
        dk_base = 0.5 * dspot + 0.5 * noisek
        if poly_lead:
            pp_lag = np.zeros(n)
            pp_lag[step:] = priv[:n - step]
            dk = dk_base + 0.4 * pp_lag
        else:
            dk = dk_base

        dk_fwd  = _rs(dk,    step)
        dp_past = _rs(dp,    step)
        ds_past = _rs(dspot, step)
        i0, i1  = step, n - step
        y_r  = dk_fwd[i0:i1]
        dp_r = dp_past[i0 - step: i1 - step]
        ds_r = ds_past[i0 - step: i1 - step]
        ok   = np.all(np.isfinite(np.column_stack([y_r, dp_r, ds_r])), axis=1)
        y_r, dp_r, ds_r = y_r[ok], dp_r[ok], ds_r[ok]
        Xr   = np.column_stack([np.ones(len(y_r)), dp_r, ds_r])
        beta, tstats = newey_west_tstat(y_r, Xr, nw_lags=NW_LAGS)

        # Cross-corr at positive lags
        mls = MAXLAG_S // GRID_S
        lags_p, corrs_p = cross_corr(dp, dk, mls)
        pos = ~np.isnan(corrs_p) & (lags_p > 0)
        if pos.any():
            pk_lag = int(lags_p[pos][np.argmax(np.abs(corrs_p[pos]))]) * GRID_S
            pk_cor = float(corrs_p[pos][np.argmax(np.abs(corrs_p[pos]))])
        else:
            pk_lag, pk_cor = 0, 0.0

        poly_t = tstats[1]
        sig    = "SIGNIFICANT" if abs(poly_t) >= 2.0 else "not significant"
        exp    = "SHOULD be significant" if poly_lead else "SHOULD NOT"
        flag   = "PASS" if ((poly_lead and abs(poly_t)>=2.0)
                            or (not poly_lead and abs(poly_t)<2.0)) else "FAIL"

        print(f"--- Scenario {label} ---")
        print(f"  Cross-corr peak (pos lags): lag={pk_lag:+d}s  corr={pk_cor:+.3f}")
        print(f"  Regression  b_poly={beta[1]:+.5f}  NW-t={poly_t:+.2f}  "
              f"b_spot={beta[2]:+.5f}  t={tstats[2]:+.2f}")
        print(f"  Result: {sig}  ({exp})  [{flag}]")
        print()


# ── entry point ────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs",  nargs="*", default=DEFAULT_DIRS)
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--grid",  type=int, default=GRID_S)
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args()

    if args.synthetic:
        print("SYNTHETIC SELF-TEST")
        print("2h data @ 2s grid. Spot leads both venues in both scenarios.")
        print("Scenario A: Poly = pure spot follower (no private signal).")
        print("Scenario B: Poly has private signal; Kalshi absorbs it 5s later.")
        run_synthetic()
        return

    run_analysis(args.dirs, asset=args.asset, grid_s=args.grid)


if __name__ == "__main__":
    main()
