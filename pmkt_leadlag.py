"""pmkt_leadlag.py -- Polymarket -> Kalshi lead-lag analysis harness.

WHY: We maker-box Kalshi KXBTC15M (15-min BTC binary) and suspect Polymarket's
deeper 5-min BTC up/down book incorporates BTC information faster.  If Polymarket
LEADS Kalshi beyond what BTC spot already tells us, that lead-time is a fair-value
signal we can embed in quote logic to reduce adverse selection on unpaired legs.
The decisive test is incremental: does the Polymarket term survive a regression that
already includes spot changes?  If not, there is nothing actionable.

    python pmkt_leadlag.py [--dirs d1 d2 ...] [--asset btc] [--grid 2]
    python pmkt_leadlag.py --synthetic          # self-test, no real data needed

Kalshi book ticks are loaded via box_policy_ab.load_window_books() (reuse, not rewrite).
Polymarket rows come from pmkt_btc_updown_*.jsonl.gz files written by pmkt_collect.py.
BTC spot comes from the 'spot' field embedded in each Kalshi book tick.

HAC/Newey-West t-stats are computed manually (no statsmodels dependency):
  sandwich = (X'X)^-1 * S * (X'X)^-1  where S is the Newey-West covariance.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import sys
from typing import List, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
DEFAULT_DIRS = ["overnight_data", "gha_data"]
GRID_S = 2          # resample grid in seconds (1 or 2)
MAX_GAP_S = 10      # drop runs where either venue was silent longer than this
MAXLAG_S = 30       # cross-correlation lag range in seconds
PRED_WINDOW_S = 5   # regression: predict ΔKalshi over next N seconds from past N seconds
NW_LAGS = 5         # Newey-West bandwidth


# ---------------------------------------------------------------------------
# REUSE BOX_POLICY_AB LOADER (Kalshi books + spot)
# ---------------------------------------------------------------------------
def _import_loader():
    """Import iter_gz and load_window_books from box_policy_ab without side effects."""
    import importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "box_policy_ab",
        os.path.join(os.path.dirname(__file__), "box_policy_ab.py"))
    mod = importlib.util.load_from_spec_if_available = None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.iter_gz, mod.load_window_books


# ---------------------------------------------------------------------------
# LOAD KALSHI + SPOT  -> (timestamps array, yes_mid array, spot array)
# ---------------------------------------------------------------------------
def load_kalshi_ticks(dirs: List[str], asset: str = "btc"):
    """Return sorted arrays (t, yes_mid, spot) from all book files found in dirs."""
    try:
        iter_gz, load_window_books = _import_loader()
    except Exception as e:
        print(f"WARNING: could not import box_policy_ab: {e}")
        iter_gz = _iter_gz_fallback
        load_window_books = None

    rows: List[Tuple[float, float, float]] = []
    for d in dirs:
        pattern_parts = [
            os.path.join(d, "**", f"book_kalshi_{asset}15m_*.jsonl.gz"),
            os.path.join(d, f"book_kalshi_{asset}15m_*.jsonl.gz"),
        ]
        seen = set()
        for pat in pattern_parts:
            for fp in glob.glob(pat, recursive=True):
                if fp in seen:
                    continue
                seen.add(fp)
                for r in iter_gz(fp):
                    if r.get("type") != "book":
                        continue
                    yb = r.get("yes") or []
                    nb = r.get("no") or []
                    if not yb or not nb:
                        continue
                    yes_bid = float(yb[-1][0])
                    no_bid = float(nb[-1][0])
                    yes_ask = round(1.0 - no_bid, 4)
                    yes_mid = (yes_bid + yes_ask) / 2.0
                    spot = r.get("spot")
                    if spot is None:
                        continue
                    rows.append((float(r["t"]), yes_mid, float(spot)))

    if not rows:
        return np.array([]), np.array([]), np.array([])
    rows.sort()
    t = np.array([x[0] for x in rows])
    mid = np.array([x[1] for x in rows])
    spot = np.array([x[2] for x in rows])
    return t, mid, spot


# ---------------------------------------------------------------------------
# LOAD POLYMARKET TICKS -> (timestamps array, up_mid array)
# ---------------------------------------------------------------------------
def load_pmkt_ticks(dirs: List[str], asset: str = "btc"):
    """Return sorted arrays (t, up_mid) from pmkt_btc_updown_*.jsonl.gz files."""
    rows: List[Tuple[float, float]] = []
    searched = []
    for d in dirs:
        patterns = [
            os.path.join(d, "**", f"pmkt_{asset}_updown_*.jsonl.gz"),
            os.path.join(d, f"pmkt_{asset}_updown_*.jsonl.gz"),
        ]
        for pat in patterns:
            searched.append(pat)
            for fp in glob.glob(pat, recursive=True):
                try:
                    with gzip.open(fp, "rt") as fh:
                        for ln in fh:
                            try:
                                r = json.loads(ln)
                            except Exception:
                                continue
                            ub = r.get("up_bid")
                            ua = r.get("up_ask")
                            if ub is None or ua is None:
                                continue
                            mid = (float(ub) + float(ua)) / 2.0
                            rows.append((float(r["t"]), mid))
                except (EOFError, OSError, gzip.BadGzipFile):
                    pass
    if not rows:
        return np.array([]), np.array([]), searched
    rows.sort()
    t = np.array([x[0] for x in rows])
    mid = np.array([x[1] for x in rows])
    return t, mid, searched


# ---------------------------------------------------------------------------
# FALLBACK iter_gz (in case import fails)
# ---------------------------------------------------------------------------
def _iter_gz_fallback(fp):
    try:
        with gzip.open(fp, "rt") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except Exception:
                    continue
    except (EOFError, OSError, gzip.BadGzipFile):
        return


# ---------------------------------------------------------------------------
# ALIGNMENT: resample to uniform grid, forward-fill, drop long-gap runs
# ---------------------------------------------------------------------------
def align_series(t_k, mid_k, t_p, mid_p, t_s, spot, grid_s=GRID_S, max_gap_s=MAX_GAP_S):
    """Resample all three series to a common grid.  Returns DataFrame with columns
    [kalshi, pmkt, spot] on a DatetimeIndex, NaN where gap > max_gap_s."""
    if len(t_k) == 0:
        return pd.DataFrame()

    t_min = max(t_k.min(), t_p.min() if len(t_p) else t_k.min())
    t_max = min(t_k.max(), t_p.max() if len(t_p) else t_k.max())
    if t_min >= t_max:
        return pd.DataFrame()

    grid = np.arange(t_min, t_max, grid_s)
    idx = pd.to_datetime(grid, unit="s", utc=True)

    def _resample(ts, vals):
        """Last-observation-carried-forward on the grid."""
        if len(ts) == 0:
            return pd.Series(np.nan, index=idx)
        s = pd.Series(vals, index=pd.to_datetime(ts, unit="s", utc=True))
        s = s[~s.index.duplicated(keep="last")]
        s = s.reindex(idx, method="ffill")
        # blank out forward-fills that span more than max_gap_s
        # find where the nearest actual observation was too far back
        last_obs = pd.Series(ts, dtype=float)
        # For each grid point, find elapsed time since last actual tick
        raw_idx = pd.to_datetime(ts, unit="s", utc=True)
        raw_s = pd.Series(vals, index=raw_idx)
        raw_s = raw_s[~raw_s.index.duplicated(keep="last")]
        # align last-tick-time onto the grid
        tick_time = pd.Series(ts, index=raw_idx)
        tick_time = tick_time[~tick_time.index.duplicated(keep="last")]
        tick_on_grid = tick_time.reindex(idx, method="ffill")
        elapsed = (grid - tick_on_grid.values)
        s[elapsed > max_gap_s] = np.nan
        return s

    df = pd.DataFrame({
        "kalshi": _resample(t_k, mid_k),
        "pmkt":   _resample(t_p, mid_p) if len(t_p) else np.nan,
        "spot":   _resample(t_s, spot),
    }, index=idx)
    return df


# ---------------------------------------------------------------------------
# CROSS-CORRELATION
# ---------------------------------------------------------------------------
def cross_corr(x: np.ndarray, y: np.ndarray, max_lag: int):
    """Return (lags, correlations) for corr(x_t, y_{t+k}) k in -max_lag..+max_lag.
    x and y must be equal-length, NaN-free."""
    n = len(x)
    lags = np.arange(-max_lag, max_lag + 1)
    corrs = np.full(len(lags), np.nan)
    sx, sy = x.std(), y.std()
    if sx == 0 or sy == 0:
        return lags, corrs
    for i, k in enumerate(lags):
        if k >= 0:
            a, b = x[:n - k], y[k:]
        else:
            a, b = x[-k:], y[:n + k]
        n_eff = len(a)
        if n_eff < 30:
            continue
        corrs[i] = float(np.corrcoef(a, b)[0, 1])
    return lags, corrs


# ---------------------------------------------------------------------------
# NEWEY-WEST HAC STANDARD ERRORS (manual vectorized, no statsmodels)
# ---------------------------------------------------------------------------
def newey_west_tstat(y: np.ndarray, X: np.ndarray, nw_lags: int = NW_LAGS):
    """OLS with Newey-West HAC t-statistics.  Returns (beta, t_stats).

    Vectorised implementation: the score matrix is score[t] = e[t] * X[t],
    then S = sum_t score[t]' score[t] + Bartlett-weighted cross-lag terms.
    No Python inner loops over observations -> O(n * lags * k^2) via matmul.
    """
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)

    # score[t] = e[t] * X[t,:]   shape (n, k)
    score = e[:, None] * X                     # (n, k)

    # Lag-0 term
    S = score.T @ score                        # (k, k)

    # Bartlett-weighted cross-lag terms (vectorised over obs)
    for lag in range(1, nw_lags + 1):
        w = 1.0 - lag / (nw_lags + 1.0)
        # score[lag:] paired with score[:-lag]
        cross = score[lag:].T @ score[:-lag]   # (k, k)
        S += w * (cross + cross.T)

    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    t_stats = np.where(se > 0, beta / se, 0.0)
    return beta, t_stats


# ---------------------------------------------------------------------------
# MAIN ANALYSIS
# ---------------------------------------------------------------------------
def run_analysis(dirs, asset="btc", grid_s=GRID_S):
    """Load data, align, run cross-corr + regression, print compact report."""
    t_k, mid_k, spot_k = load_kalshi_ticks(dirs, asset)
    t_p, mid_p, searched = load_pmkt_ticks(dirs, asset)

    if len(t_p) == 0:
        print("=" * 60)
        print("NO POLYMARKET DATA YET -- rerun after collection accumulates.")
        print("Searched globs:")
        for s in searched:
            print(f"  {s}")
        print("=" * 60)
        if len(t_k) > 0:
            span_h = (t_k.max() - t_k.min()) / 3600
            print(f"Kalshi data available: {span_h:.1f}h, {len(t_k)} ticks")
        return

    df = align_series(t_k, mid_k, t_p, mid_p, spot_k, spot_k, grid_s=grid_s)
    if df.empty or len(df.dropna()) < 100:
        print("Insufficient overlapping data after alignment (need >=100 rows, no-gap).")
        return

    # Coverage summary
    aligned_h = len(df) * grid_s / 3600
    n_full = df.dropna().shape[0]
    n_gaps = df.isna().any(axis=1).sum()
    print("=" * 60)
    print(f"DATA COVERAGE")
    print(f"  Aligned span : {aligned_h:.2f}h  ({len(df)} grid points @ {grid_s}s)")
    print(f"  Full (no gap): {n_full} rows  |  Gap rows: {n_gaps}")
    print(f"  Kalshi ticks : {len(t_k)}  |  Pmkt ticks: {len(t_p)}")

    # Work on diff series (changes = returns), drop NaN
    clean = df.dropna()
    dk = clean["kalshi"].diff().dropna()
    dp = clean["pmkt"].diff().dropna()
    ds = clean["spot"].diff().dropna()
    # align all three to the same index
    common = dk.index.intersection(dp.index).intersection(ds.index)
    dk = dk.loc[common].values
    dp = dp.loc[common].values
    ds = ds.loc[common].values
    n = len(dk)
    if n < 60:
        print("Fewer than 60 aligned diff-rows; cannot compute statistics.")
        return

    # ----- CROSS-CORRELATION -----
    max_lag_steps = MAXLAG_S // grid_s
    lags_p, corrs_p = cross_corr(dp, dk, max_lag_steps)
    lags_s, corrs_s = cross_corr(ds, dk, max_lag_steps)

    def _peak(lags, corrs):
        valid = ~np.isnan(corrs)
        if not valid.any():
            return 0, 0.0
        idx = np.argmax(np.abs(corrs[valid]))
        return int(lags[valid][idx]) * grid_s, float(corrs[valid][idx])

    pk_lag_p, pk_corr_p = _peak(lags_p, corrs_p)
    pk_lag_s, pk_corr_s = _peak(lags_s, corrs_s)

    print()
    print("CROSS-CORRELATION (lag > 0 => Poly/Spot leads Kalshi)")
    print(f"  {'Source':<8} {'Peak lag (s)':>13} {'Peak corr':>10}  {'Interpretation'}")
    print(f"  {'Pmkt':<8} {pk_lag_p:>+13}  {pk_corr_p:>+10.3f}  "
          f"{'Poly LEADS Kalshi' if pk_lag_p > 0 else 'no lead or Kalshi leads'}")
    print(f"  {'Spot':<8} {pk_lag_s:>+13}  {pk_corr_s:>+10.3f}  "
          f"{'Spot LEADS Kalshi' if pk_lag_s > 0 else 'no spot lead'}")

    # Show top-5 rows around the Poly peak
    print()
    print("  Poly->Kalshi cross-corr near peak (top-5 by |corr|):")
    valid_mask = ~np.isnan(corrs_p)
    order = np.argsort(-np.abs(corrs_p[valid_mask]))[:5]
    for i in order:
        lag_s_val = int(lags_p[valid_mask][i]) * grid_s
        c = corrs_p[valid_mask][i]
        print(f"    lag={lag_s_val:+4d}s  corr={c:+.4f}")

    # ----- INCREMENTAL REGRESSION -----
    step = max(1, PRED_WINDOW_S // grid_s)
    # ΔKalshi_{t -> t+step}: future = mid[t+step] - mid[t]
    # ΔPoly_{t-step -> t}: past Poly = mid[t] - mid[t-step]
    # ΔSpot_{t-step -> t}: past Spot = spot[t] - spot[t-step]
    clean2 = df.dropna()
    K = clean2["kalshi"].values
    P = clean2["pmkt"].values
    S = clean2["spot"].values
    N2 = len(K)
    if N2 < 2 * step + 30:
        print("Not enough rows for regression after step differencing.")
        return

    y_reg  = K[step:] - K[:-step]          # ΔKalshi forward
    dp_reg = P[step:] - P[:N2 - step]      # ΔPoly "past" (shifted: dp[t]=P[t]-P[t-step])
    ds_reg = S[step:] - S[:N2 - step]      # ΔSpot "past"
    # Align: y is future (t+step), dp/ds are lagged (t vs t-step)
    # We want: y_{t+step} ~ dp_{t-step->t} + ds_{t-step->t}
    # With the arrays above: y_reg[i] = K[i+step]-K[i], dp_reg[i] = P[i+step]-P[i] (forward not past)
    # Re-do: past changes end at t, future change starts at t
    min_i = step
    max_i = N2 - step
    y_reg2  = K[min_i + step: max_i + step] - K[min_i: max_i]   # forward ΔKalshi
    dp_past = P[min_i: max_i] - P[min_i - step: max_i - step]   # past ΔPoly ending at t
    ds_past = S[min_i: max_i] - S[min_i - step: max_i - step]   # past ΔSpot ending at t

    # Drop NaN rows
    stk = np.column_stack([y_reg2, dp_past, ds_past])
    ok = np.all(np.isfinite(stk), axis=1)
    stk = stk[ok]
    if stk.shape[0] < 30:
        print("Not enough clean rows for regression.")
        return
    y_r, dp_r, ds_r = stk[:, 0], stk[:, 1], stk[:, 2]
    X_r = np.column_stack([np.ones(len(y_r)), dp_r, ds_r])
    beta_r, tstat_r = newey_west_tstat(y_r, X_r, nw_lags=NW_LAGS)

    print()
    print(f"INCREMENTAL REGRESSION  (Δ over {PRED_WINDOW_S}s windows, HAC NW lags={NW_LAGS})")
    print(f"  ΔKalshi_forward ~ const + β_poly·ΔPoly_past + β_spot·ΔSpot_past")
    print(f"  n = {len(y_r)} observations")
    print(f"  {'Term':<12} {'β':>10} {'NW t-stat':>10}  {'Sig?':>5}")
    names = ["const", "Δpoly", "Δspot"]
    for nm, b, t in zip(names, beta_r, tstat_r):
        sig = "***" if abs(t) > 3.0 else ("**" if abs(t) > 2.0 else ("*" if abs(t) > 1.65 else ""))
        print(f"  {nm:<12} {b:>+10.5f} {t:>+10.2f}  {sig:>5}")

    # ----- VERDICT -----
    poly_t = tstat_r[1]
    print()
    print("VERDICT")
    if abs(poly_t) >= 2.0:
        direction = "LEADS" if tstat_r[1] > 0 else "INVERSELY LEADS"
        # Economic translation: 1 tick = 0.01 Kalshi cents; estimate implied edge
        poly_b = beta_r[1]
        # Typical Poly move in 5s (IQR of dp_r)
        typical_dp = np.percentile(np.abs(dp_r[dp_r != 0]), 75) if (dp_r != 0).any() else 0.0
        implied_edge_cents = abs(poly_b * typical_dp) * 100  # in ¢ per quote
        print(f"  ACTIONABLE: Poly {direction} Kalshi (t={poly_t:+.2f} >= 2.0).")
        print(f"  β_poly = {poly_b:+.5f};  typical ΔPoly (75th pct) = {typical_dp:.4f}")
        print(f"  Implied edge ≈ {implied_edge_cents:.3f}¢ per Kalshi quote-adjustment opportunity.")
    else:
        print(f"  NOT SIGNIFICANT (t={poly_t:+.2f}). Poly adds no incremental info beyond spot.")
        print(f"  Recommendation: do NOT add Polymarket-based quote adjustments.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# SYNTHETIC SELF-TEST
# ---------------------------------------------------------------------------
def run_synthetic():
    """Generate 2h synthetic series (2s grid = 3600 obs) and verify:
      Scenario A: spot leads both venues, Poly has NO extra info -> poly t-stat insignificant.
      Scenario B: Poly ALSO leads Kalshi by 5s beyond spot -> poly t-stat significant.
    """
    rng = np.random.default_rng(42)
    n = 3600         # 2h @ 2s
    grid_s = 2
    step = PRED_WINDOW_S // grid_s   # 2 steps = 5s lag

    def _make_scenario(poly_lead: bool):
        """Return (k_mid, p_mid, spot_arr) as arrays of length n.

        Series are built entirely in *changes* space to stay stationary:
          - BTC spot: random walk increments (price level irrelevant here).
          - Pmkt/Kalshi: increments correlated with spot increments + idio noise.
          - In scenario B, ΔKalshi[t] += 0.4 * ΔPoly[t-step] on top of spot signal.
        For regression we use the change series directly.  Level arrays are the
        cumsum (mid-probability path), used only for cross-corr sanity checks.
        """
        # Small-scale spot increments (log-price changes, ~0.1% per 2s)
        dspot = rng.normal(0, 0.001, n)         # log-return increments

        # Poly change: 0.5 weight on spot, 0.5 independent noise
        dp = 0.5 * dspot + 0.5 * rng.normal(0, 0.001, n)

        # Kalshi change base: 0.5 weight on spot, 0.5 independent noise
        dk_base = 0.5 * dspot + 0.5 * rng.normal(0, 0.001, n)

        if poly_lead:
            # Δkalshi[t] += 0.4 * Δpoly[t - step] (Poly leads Kalshi)
            dp_lagged = np.zeros(n)
            dp_lagged[step:] = dp[:n - step]
            dk = dk_base + 0.4 * dp_lagged
        else:
            dk = dk_base

        # Build level series from increments (arbitrary starting point)
        spot_val = 60000.0 * np.exp(np.cumsum(dspot))
        p_mid = np.clip(0.50 + 10.0 * np.cumsum(dp), 0.01, 0.99)
        k_mid = np.clip(0.50 + 10.0 * np.cumsum(dk), 0.01, 0.99)
        return k_mid, p_mid, spot_val, dk, dp, dspot

    for label, poly_lead in [("A (no Poly lead, spot-only)", False),
                              ("B (Poly leads Kalshi by 5s)", True)]:
        k, p, s, dk, dp, dspot = _make_scenario(poly_lead)

        # Regression operates on change arrays directly (not level diffs) to avoid
        # the clipping-to-constant issue that afflicts level cumsum series.
        # y  = Δkalshi_{t -> t+step}  = sum of next `step` dk increments
        # xp = Δpoly_{t-step -> t}   = sum of previous `step` dp increments
        # xs = Δspot_{t-step -> t}   = sum of previous `step` dspot increments
        # We build rolling sums of length `step` via cumsum.
        def _rolling_sum(arr, w):
            cs = np.concatenate([[0.0], np.cumsum(arr)])
            return cs[w:] - cs[:-w]

        # _rolling_sum is a FORWARD window: roll[j] = sum arr[j : j+step].
        roll_dk = _rolling_sum(dk, step)
        roll_dp = _rolling_sum(dp, step)
        roll_ds = _rolling_sum(dspot, step)

        # For each obs at grid index t (step <= t < n-step):
        #   y[t]  = sum dk[t : t+step]      = roll_dk[t]        (FUTURE Kalshi change)
        #   xp[t] = sum dp[t-step : t]      = roll_dp[t-step]   (PAST Poly change ending at t)
        #   xs[t] = sum dspot[t-step : t]   = roll_ds[t-step]
        i0, i1 = step, n - step
        y_r  = roll_dk[i0:i1]
        dp_r = roll_dp[i0 - step:i1 - step]
        ds_r = roll_ds[i0 - step:i1 - step]

        ok = np.all(np.isfinite(np.column_stack([y_r, dp_r, ds_r])), axis=1)
        y_r, dp_r, ds_r = y_r[ok], dp_r[ok], ds_r[ok]
        X_r = np.column_stack([np.ones(len(y_r)), dp_r, ds_r])
        beta_r, tstat_r = newey_west_tstat(y_r, X_r, nw_lags=NW_LAGS)

        # cross-corr peak on full change series
        max_lag_steps = MAXLAG_S // grid_s
        lags_p, corrs_p = cross_corr(dp, dk, max_lag_steps)
        valid = ~np.isnan(corrs_p)
        pk_lag = int(lags_p[valid][np.argmax(np.abs(corrs_p[valid]))]) * grid_s if valid.any() else 0
        pk_corr = float(corrs_p[valid][np.argmax(np.abs(corrs_p[valid]))]) if valid.any() else 0.0

        poly_t = tstat_r[1]
        sig = "SIGNIFICANT (actionable)" if abs(poly_t) >= 2.0 else "not significant"
        expected = "SHOULD be significant" if poly_lead else "SHOULD NOT be significant"
        ok_flag = ("PASS" if (poly_lead and abs(poly_t) >= 2.0)
                   or (not poly_lead and abs(poly_t) < 2.0) else "FAIL")

        print(f"--- Scenario {label} ---")
        print(f"  Cross-corr peak: lag={pk_lag:+d}s  corr={pk_corr:+.3f}")
        print(f"  Regression  β_poly={beta_r[1]:+.5f}  NW-t={poly_t:+.2f}  "
              f"β_spot={beta_r[2]:+.5f}  t={tstat_r[2]:+.2f}")
        print(f"  Result: {sig}  ({expected})  [{ok_flag}]")
        print()


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Polymarket->Kalshi lead-lag analysis")
    ap.add_argument("--dirs", nargs="*", default=DEFAULT_DIRS,
                    help="Data directories to search (default: overnight_data gha_data)")
    ap.add_argument("--asset", default="btc", help="Asset (default: btc)")
    ap.add_argument("--grid", type=int, default=GRID_S,
                    help=f"Resample grid in seconds (default: {GRID_S})")
    ap.add_argument("--synthetic", action="store_true",
                    help="Run synthetic self-test mode (no real data needed)")
    args = ap.parse_args()

    if args.synthetic:
        print("SYNTHETIC SELF-TEST")
        print("2h of synthetic data, spot leads both venues.")
        print("Scenario A: Poly has NO incremental info (pure spot follower).")
        print("Scenario B: Poly ALSO leads Kalshi by 5s beyond spot.")
        print()
        run_synthetic()
        return

    run_analysis(args.dirs, asset=args.asset, grid_s=args.grid)


if __name__ == "__main__":
    main()
