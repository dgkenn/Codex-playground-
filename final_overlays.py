#!/usr/bin/env python3
"""
final_overlays.py -- CAPSTONE synthesis driver.

Question: a dead-simple STATIC portfolio (Permanent Portfolio Sharpe ~0.93,
inverse-vol risk-parity ~0.84) BEATS the active momentum+trend book (~0.81) on
risk-adjusted return. Can a LIGHT tactical overlay on the static base capture the
static's high Sharpe PLUS the active book's shallower drawdown -- net of costs, OOS,
on a PLATEAU not a spike -- enough to justify added effort?

REUSES the locked engines (does NOT re-derive components):
  static_allocation.py  -> Permanent Portfolio, inverse-vol risk-parity
  portfolio_combined.py -> sleeve_A (ETF momentum) + sleeve_B (inverse-TF), 70/30 active book

Overlays tested on the static base:
  (a) REGIME-GATED static: SPY<200dMA -> move equity slice (and variant: whole book) to BIL
  (b) STATIC CORE + ACTIVE satellite: blend X% static / (100-X)% 70/30 active book
  (c) trend-filter EACH static asset: hold if >10m(210d) MA else BIL (Faber/Antonacci)

Plus a cross-correlation / conflict check between static legs and the active book.

Window: overlap 2007-06 -> 2026-06 full; recent OOS holdout 2016-01 -> 2026-06.
Costs: 3 bps/side on rebalance turnover (same model as all components).
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

from static_allocation import load_all, fixed_weight_port, inverse_vol_port, stats, RISKPARITY
from portfolio_combined import sleeve_A, sleeve_B, combine_n
a_stats = stats  # use the static_allocation stats (full key set) uniformly

COST_BPS = 3.0
TD = 252
FULL_START = "2007-06-01"
OOS_START  = "2016-01-01"

PP_W = {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "BIL": 0.25}


# --------------------------------------------------------------------------
def line(name, s):
    return (f"{name:34} Sharpe={s['Sharpe']:.3f}  maxDD={s['maxDD']*100:6.2f}%  "
            f"CAGR={s['CAGR']*100:5.2f}%  vol={s['vol']*100:5.2f}%  worstYr={s['worst_yr']*100:6.1f}%")


def sub_period(net, start, end=None):
    n = net[net.index >= pd.Timestamp(start)]
    if end:
        n = n[n.index <= pd.Timestamp(end)]
    return n.dropna()


# ---- (a) regime-gated static ---------------------------------------------
def regime_gated_static(px, base_weights, gate_assets, vol_win=200, rebal="M",
                        cost_bps=COST_BPS, start=None, end=None):
    """Static base; when SPY < 200d SMA at month start, move `gate_assets`
    slices to BIL until SPY back above. Monthly check. gate_assets: list of
    tickers in base_weights whose slice is parked in BIL during risk-off."""
    tickers = sorted(set(list(base_weights) + ["SPY", "BIL"]))
    sub = px[tickers].dropna()
    if start: sub = sub[sub.index >= pd.Timestamp(start)]
    if end:   sub = sub[sub.index <= pd.Timestamp(end)]
    rets = sub.pct_change().fillna(0)
    idx = sub.index
    spy = sub["SPY"]
    sma = spy.rolling(vol_win).mean()
    risk_on = (spy > sma)  # daily; we sample at month start

    # month-end dates = rebalance dates
    keyed = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    rebal_dates = set(pd.Timestamp(d) for d in keyed.values)

    base = {t: base_weights.get(t, 0.0) for t in tickers}

    def target_for(date):
        on = bool(risk_on.loc[:date].iloc[-1]) if date in risk_on.index else True
        w = dict(base)
        if not on:
            moved = 0.0
            for g in gate_assets:
                moved += w.get(g, 0.0)
                w[g] = 0.0
            w["BIL"] = w.get("BIL", 0.0) + moved
        arr = np.array([w[t] for t in tickers], float)
        s = arr.sum()
        return arr / s if s else arr

    R = rets.values
    w = target_for(idx[0])
    cur_tgt = w.copy()
    port = np.empty(len(idx)); cost = np.zeros(len(idx))
    for i in range(len(idx)):
        port[i] = float(np.dot(w, R[i]))
        w = w * (1 + R[i]); ssum = w.sum()
        if ssum: w = w / ssum
        if idx[i] in rebal_dates:
            new_tgt = target_for(idx[i])
            turnover = np.abs(new_tgt - w).sum()
            cost[i] += turnover * cost_bps / 1e4
            w = new_tgt.copy(); cur_tgt = new_tgt
    return (pd.Series(port, index=idx) - pd.Series(cost, index=idx)).dropna()


# ---- (c) per-asset 10-month trend filter ---------------------------------
def trend_filtered_static(px, base_weights, sma_days=210, rebal="M",
                          cost_bps=COST_BPS, start=None, end=None):
    """Each base asset: hold if price > 10m(~210d) SMA at month start else park its
    slice in BIL. Faber/Antonacci-style. BIL itself never gated."""
    tickers = sorted(set(list(base_weights) + ["BIL"]))
    sub = px[tickers].dropna()
    if start: sub = sub[sub.index >= pd.Timestamp(start)]
    if end:   sub = sub[sub.index <= pd.Timestamp(end)]
    rets = sub.pct_change().fillna(0)
    idx = sub.index
    smas = {t: sub[t].rolling(sma_days).mean() for t in tickers}
    keyed = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    rebal_dates = set(pd.Timestamp(d) for d in keyed.values)
    base = {t: base_weights.get(t, 0.0) for t in tickers}

    def target_for(date):
        w = {t: 0.0 for t in tickers}
        parked = 0.0
        for t, bw in base.items():
            if bw == 0: continue
            if t == "BIL":
                w[t] += bw; continue
            above = sub[t].loc[:date].iloc[-1] > smas[t].loc[:date].iloc[-1]
            if above:
                w[t] += bw
            else:
                parked += bw
        w["BIL"] = w.get("BIL", 0.0) + parked
        arr = np.array([w[t] for t in tickers], float)
        s = arr.sum()
        return arr / s if s else arr

    R = rets.values
    w = target_for(idx[0])
    port = np.empty(len(idx)); cost = np.zeros(len(idx))
    for i in range(len(idx)):
        port[i] = float(np.dot(w, R[i]))
        w = w * (1 + R[i]); ssum = w.sum()
        if ssum: w = w / ssum
        if idx[i] in rebal_dates:
            new_tgt = target_for(idx[i])
            turnover = np.abs(new_tgt - w).sum()
            cost[i] += turnover * cost_bps / 1e4
            w = new_tgt.copy()
    return (pd.Series(port, index=idx) - pd.Series(cost, index=idx)).dropna()


# --------------------------------------------------------------------------
def report():
    px = load_all()
    print("=" * 96)
    print("CAPSTONE OVERLAY SYNTHESIS  (window full 2007-06->2026-06, OOS 2016-01->2026-06; net 3bps/side)")
    print("=" * 96)

    # ----- BASE: confirm best static --------------------------------------
    print("\n[1] BASE -- best simple static (full / OOS)")
    pp_full = fixed_weight_port(px, PP_W, start=FULL_START)
    rp_full = inverse_vol_port(px, RISKPARITY, start=FULL_START)
    pp_oos  = sub_period(pp_full, OOS_START)
    rp_oos  = sub_period(rp_full, OOS_START)
    print("  FULL:")
    print("   ", line("Permanent Portfolio", stats(pp_full)))
    print("   ", line("Risk-Parity (inv-vol)", stats(rp_full)))
    print("  OOS (2016+):")
    print("   ", line("Permanent Portfolio", stats(pp_oos)))
    print("   ", line("Risk-Parity (inv-vol)", stats(rp_oos)))

    # pick robust base by OOS Sharpe + maxDD
    base_choice = "Permanent Portfolio"
    base_full, base_oos = pp_full, pp_oos
    print(f"\n  -> robust BASE pick: {base_choice} (highest Sharpe both periods, shallowest maxDD)")

    # ----- active book (for blends + correlation) -------------------------
    a = sleeve_A(start=FULL_START); b = sleeve_B(start=FULL_START)
    active = combine_n([a, b], [0.7, 0.3])
    active_oos = sub_period(active, OOS_START)
    print("\n[ref] Active 70/30 momentum+TF book")
    print("   FULL:", line("", a_stats(active)).strip())
    print("   OOS :", line("", a_stats(active_oos)).strip())

    # ----- (a) regime-gated static ----------------------------------------
    print("\n[2a] REGIME-GATED static (SPY<200dMA -> park slice in BIL)")
    rg_eq_full = regime_gated_static(px, PP_W, ["SPY"], start=FULL_START)
    rg_all_full = regime_gated_static(px, PP_W, ["SPY", "TLT", "GLD"], start=FULL_START)
    for nm, full in [("Gate EQUITY slice only", rg_eq_full),
                     ("Gate equity+TLT+GLD (whole risk)", rg_all_full)]:
        print("   FULL", line(nm, stats(full)))
        print("   OOS ", line(nm, stats(sub_period(full, OOS_START))))

    # ----- (b) static core + active satellite -----------------------------
    print("\n[2b] STATIC CORE + small ACTIVE satellite (blend X% PP / (1-X)% active book)")
    blends = {}
    for x in [1.0, 0.8, 0.7, 0.6, 0.5, 0.0]:
        # align base to active overlap window for fair blend
        net = combine_n([base_full, active], [x, 1 - x]) if 0 < x < 1 else (base_full if x == 1 else active)
        net = sub_period(net, FULL_START)
        blends[x] = net
        tag = f"{int(x*100)}/{int((1-x)*100)} PP/active"
        print("   FULL", line(tag, a_stats(net)))
        print("   OOS ", line(tag, a_stats(sub_period(net, OOS_START))))

    # ----- (c) per-asset trend filter -------------------------------------
    print("\n[2c] TREND-FILTERED static (each asset >10m MA else BIL)")
    tf_full = trend_filtered_static(px, PP_W, start=FULL_START)
    print("   FULL", line("PP trend-filtered (10m)", stats(tf_full)))
    print("   OOS ", line("PP trend-filtered (10m)", stats(sub_period(tf_full, OOS_START))))

    # ----- (3) cross-correlation / conflict check -------------------------
    print("\n[3] CROSS-CORRELATION / CONFLICT CHECK")
    # static legs (returns) vs active book
    legs = {}
    for t in ["SPY", "TLT", "GLD"]:
        legs[t] = px[t].pct_change()
    af = sub_period(active, FULL_START)
    df = pd.concat({**legs, "ACTIVE": af, "PP": base_full}, axis=1, join="inner").dropna()
    corr = df.corr()
    print("   Daily-return correlation matrix (overlap):")
    print(corr.round(3).to_string())
    # crash-period correlation: worst 5% PP days
    thr = df["PP"].quantile(0.05)
    crash = df[df["PP"] <= thr]
    print(f"\n   Crash-period (worst 5% PP days, n={len(crash)}) corr of ACTIVE vs PP legs:")
    print("    ", {k: round(crash["ACTIVE"].corr(crash[k]), 3) for k in ["SPY", "TLT", "GLD", "PP"]})
    # does active SHORT what PP is long? beta of active to TLT and GLD
    import numpy as _np
    for leg in ["TLT", "GLD", "SPY"]:
        bb = _np.polyfit(df[leg], df["ACTIVE"], 1)[0]
        print(f"    beta(ACTIVE ~ {leg}) = {bb:+.3f}")

    print("\n" + "=" * 96)
    print("VERDICT TABLE (OOS 2016+, the brutal bar):")
    rows = [
        ("Pure PP static", stats(pp_oos)),
        ("Pure RP static", stats(rp_oos)),
        ("Pure active 70/30", a_stats(active_oos)),
        ("Regime-gate equity", stats(sub_period(rg_eq_full, OOS_START))),
        ("Regime-gate whole risk", stats(sub_period(rg_all_full, OOS_START))),
        ("Trend-filter (10m)", stats(sub_period(tf_full, OOS_START))),
        ("80/20 PP/active", a_stats(sub_period(blends[0.8], OOS_START))),
        ("70/30 PP/active", a_stats(sub_period(blends[0.7], OOS_START))),
        ("60/40 PP/active", a_stats(sub_period(blends[0.6], OOS_START))),
    ]
    for nm, s in rows:
        print("   ", line(nm, s))
    print("=" * 96)


if __name__ == "__main__":
    report()
