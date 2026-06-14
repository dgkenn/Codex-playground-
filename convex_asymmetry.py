#!/usr/bin/env python3
"""
convex_asymmetry.py -- Find the best DATA-INFORMED, CONVEX, POSITIVE-SKEW-AND-
POSITIVE-EV high-upside sleeve for a high-risk-tolerant small-bankroll US
investor, and the optimal BARBELL sizing against a safe base.

CORE THESIS (what "disproportionate positive return" means here):
  disproportionate-positive = positive SKEW + high upside/downside asymmetry
  WHILE STILL +EV. Reject high-skew NEGATIVE-EV bets (OTM calls, lotto alts,
  buy-hold junk). Reject negative-skew +EV bets (selling vol, carry). The rare
  both-positive combination is TREND-FOLLOWING on volatile assets: it lets the
  right tail run (BTC 10x) and cuts the left tail (trend exit) -> positive skew
  AND positive EV.

This script REUSES the committed engine logic:
  - btc_trend_timing.sma_signal / backtest / perf  (the base convex engine)
  - trend_following / allweather trend-gate idea (sleeve d, conceptual)
  - the safe base = trend-overlaid all-weather (modelled here from SPY/TLT/GLD/BIL
    with the same 12m trend gate the repo's allweather_live uses), Sharpe ~1.1-1.4.

Data: /tmp/convex_data/prices.csv (yfinance daily, NOT committed).
Costs: crypto spot round-trip charged PER SIDE on each switch (default 20 bps/side
  = 40 bps round trip), matching btc_trend_timing. LETF: explicit daily financing +
  expense + path-decay modelled honestly. Gap risk modelled in Monte-Carlo.

Outputs CONVEX_ASYMMETRY.md + a results json. SCREENS what fails the +EV bar.
"""
from __future__ import annotations
import numpy as np, pandas as pd, json, sys
from scipy import stats as sps

# reuse committed engine pieces
from btc_trend_timing import sma_signal, backtest as bt_backtest, perf

DATA = "/tmp/convex_data/prices.csv"
TD_CRYPTO = 365     # crypto is 7d/wk calendar-daily
TD_EQ = 252
RNG = np.random.default_rng(20260614)


def load():
    px = pd.read_csv(DATA, index_col=0, parse_dates=True).sort_index()
    return px


# ---------------------------------------------------------------------------
# ASYMMETRY / CONVEXITY METRICS  (the rigorous definitions)
# ---------------------------------------------------------------------------
def asym_metrics(daily_rets, freq=TD_CRYPTO, horizon_days=None):
    """Compute the disproportionate-positive metric battery on a daily return series.

    Returns dict with:
      CAGR, mean_ann (EV proxy), vol, Sharpe, maxDD, skew (daily & monthly),
      tail_ratio = p95 / |p5| of returns (monthly, robust),
      omega (threshold 0), up_capture/down_capture vs the asset's own up/down days,
      and -- via bootstrap of `horizon_days` windows -- P(>2x), P(>5x), P(<0.5x/ruin).
    DISPRO score is computed separately (requires +EV gate).
    """
    r = pd.Series(daily_rets).dropna()
    if len(r) < 60:
        return None
    eq = (1 + r).cumprod()
    yrs = len(r) / freq
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    mean_ann = r.mean() * freq
    vol = r.std() * np.sqrt(freq)
    sharpe = mean_ann / vol if vol > 0 else np.nan
    dd = eq / eq.cummax() - 1
    maxdd = dd.min()
    skew_d = sps.skew(r.values)
    # monthly aggregation for less-noisy skew / tail ratio
    m = (1 + r).resample("ME").prod() - 1 if hasattr(r.index, "freq") or True else None
    try:
        m = (1 + r).resample("ME").prod() - 1
    except Exception:
        m = r
    m = m.dropna()
    skew_m = sps.skew(m.values) if len(m) > 10 else np.nan
    p95 = np.percentile(m, 95); p5 = np.percentile(m, 5)
    tail_ratio = p95 / abs(p5) if p5 != 0 else np.nan
    # Omega ratio at 0 (monthly): E[gains]/E[losses]
    gains = m[m > 0].sum(); losses = -m[m < 0].sum()
    omega = gains / losses if losses > 0 else np.nan
    return dict(CAGR=cagr, mean_ann=mean_ann, vol=vol, Sharpe=sharpe, maxDD=maxdd,
                skew_d=skew_d, skew_m=skew_m, tail_ratio=tail_ratio, omega=omega,
                n=len(r), yrs=yrs, daily=r)


def bootstrap_horizon(daily_rets, horizon_days, n_boot=4000, block=20, haircut_ann=0.0):
    """Stationary-block bootstrap of compounded horizon returns.
    haircut_ann: subtract this annualized drift (decimal) from daily mean to HAIRCUT
                 the right tail / mean (humility about short crypto sample).
    Returns array of horizon multiples (1.0 = breakeven)."""
    r = pd.Series(daily_rets).dropna().values
    n = len(r)
    if n < horizon_days // 2:
        return None
    hair_d = haircut_ann / TD_CRYPTO
    r = r - hair_d
    out = np.empty(n_boot)
    for i in range(n_boot):
        idx = []
        while len(idx) < horizon_days:
            start = RNG.integers(0, n)
            L = min(RNG.geometric(1.0 / block), horizon_days - len(idx))
            seg = np.arange(start, start + L) % n
            idx.extend(seg.tolist())
        seg = r[np.array(idx[:horizon_days])]
        out[i] = np.prod(1 + seg)
    return out


def prob_table(mult):
    """From an array of horizon multiples -> probabilities."""
    return dict(median=float(np.median(mult)),
                p5=float(np.percentile(mult, 5)),
                p25=float(np.percentile(mult, 25)),
                p75=float(np.percentile(mult, 75)),
                p95=float(np.percentile(mult, 95)),
                P_2x=float(np.mean(mult >= 2.0)),
                P_5x=float(np.mean(mult >= 5.0)),
                P_half=float(np.mean(mult < 0.5)),
                P_ruin=float(np.mean(mult < 0.1)))


# ---------------------------------------------------------------------------
# SLEEVE BUILDERS -> daily net return series
# ---------------------------------------------------------------------------
def cash_daily(px):
    return px["BIL"].pct_change()


def trend_timed(px, asset, ma=200, cost_bps=20.0, cadence="weekly", start=None):
    """Reuse btc_trend_timing: SMA(ma) trend gate, cash=BIL when out."""
    s = px[asset].dropna()
    if start:
        s = s[s.index >= start]
    cr = px["BIL"].pct_change().reindex(s.index)
    sig = sma_signal(s, ma)
    strat, pos, nsw = bt_backtest(s, sig, cr, cost_bps, cadence)
    return strat.dropna(), pos


def buyhold(px, asset, start=None):
    s = px[asset].dropna()
    if start:
        s = s[s.index >= start]
    return s.pct_change().dropna()


def trend_basket(px, assets, ma=200, cost_bps=20.0, cadence="weekly", start=None):
    """Equal-weight basket of trend-gated assets; each leg trend-gated to cash."""
    legs = []
    for a in assets:
        if a not in px.columns:
            continue
        st, _ = trend_timed(px, a, ma, cost_bps, cadence, start)
        legs.append(st.rename(a))
    if not legs:
        return None
    M = pd.concat(legs, axis=1)
    # equal weight across legs that exist on each day (so SOL/ETH joining later is fine)
    return M.mean(axis=1, skipna=True).dropna()


def letf_trend(px, asset, lev=2.0, ma=200, cost_bps=20.0, cadence="weekly",
               start=None, financing_ann=0.06, expense_ann=0.0095):
    """Leveraged trend-timed crypto: lev x DAILY return WHILE trend up, cash when down.
    The trend gate caps the left tail of leverage. Honest modelling:
      daily levered return = lev * asset_daily  - (lev-1)*financing/365 - expense/365
      (path decay emerges naturally from daily compounding of lev*r).
    cost charged on switches. Out-of-market earns BIL.
    """
    s = px[asset].dropna()
    if start:
        s = s[s.index >= start]
    ar = s.pct_change()
    cr = px["BIL"].pct_change().reindex(s.index).fillna(0)
    sig = sma_signal(s, ma)
    # cadence gate (weekly) same as backtest
    if cadence == "weekly":
        allow = s.index.to_series().dt.dayofweek == 0
    elif cadence == "monthly":
        allow = s.index.to_series().groupby([s.index.year, s.index.month]).transform(
            lambda x: x.index == x.index.min())
    else:
        allow = pd.Series(True, index=s.index)
    target = sig.where(allow).ffill().fillna(0)
    pos = target.shift(1).fillna(0)
    daily_drag = ((lev - 1) * financing_ann + expense_ann) / 365.0
    lev_ret = lev * ar - daily_drag
    gross = pos * lev_ret + (1 - pos) * cr
    dpos = pos.diff().abs().fillna(0)
    cost = dpos * lev * (cost_bps / 1e4)   # cost scales with levered notional
    strat = (gross - cost).dropna()
    return strat, pos


def naive_letf_buyhold(px, asset, lev=3.0, start=None, financing_ann=0.06,
                       expense_ann=0.0095):
    """CONTRAST (should FAIL): naive 3x LETF buy-and-hold, no trend gate.
    Daily lev compounding + financing/expense drag. No left-tail cap."""
    s = px[asset].dropna()
    if start:
        s = s[s.index >= start]
    ar = s.pct_change()
    daily_drag = ((lev - 1) * financing_ann + expense_ann) / 365.0
    lev_ret = (lev * ar - daily_drag)
    # floor a single day at -100% (LETF can't go below -100% intraday reset, but daily
    # -33% move * 3 = -100% -> wipeout). Model wipeout: if levered daily < -1, equity->0.
    lev_ret = lev_ret.clip(lower=-0.999)
    return lev_ret.dropna()


def otm_call_proxy(px, asset, start=None, otm_pct=0.30, prem_pct=0.08, tenor_d=30):
    """CONTRAST (should FAIL on EV): rolling monthly 30%-OTM call buying proxy.
    Pay prem_pct of notional per month; collect max(0, ret_month - otm_pct).
    Hugely positive skew, but bleeds premium -> negative EV. We model it simply:
    each month invest 100%, return = max(0, S_T/S_0 - 1 - otm_pct) - prem_pct.
    """
    s = px[asset].dropna()
    if start:
        s = s[s.index >= start]
    m = s.resample("ME").last()
    mr = m.pct_change().dropna()
    payoff = np.maximum(0.0, mr.values - otm_pct) - prem_pct
    return pd.Series(payoff, index=mr.index)


# ---------------------------------------------------------------------------
# SAFE BASE: trend-overlaid all-weather (reuses allweather idea: 12m TS-trend
# gate each risk sleeve SPY/TLT/GLD to BIL, BIL always cash). Equal 25% weights.
# ---------------------------------------------------------------------------
def safe_base(px, start=None, cost_bps=3.0):
    cols = ["SPY", "TLT", "GLD", "BIL"]
    P = px[cols].dropna()
    if start:
        P = P[P.index >= start]
    rets = P.pct_change()
    cash = rets["BIL"].fillna(0)
    # 12m (252d) trend gate per risk sleeve
    daily_port = pd.Series(0.0, index=P.index)
    weights_prev = {}
    pos_frames = {}
    for a in ["SPY", "TLT", "GLD"]:
        trail = P[a] / P[a].shift(252) - 1
        on = (trail > 0).astype(float).shift(1).fillna(0)  # act next day
        pos_frames[a] = on
    # build daily returns: each sleeve 25%; risk sleeve uses asset ret if on else cash
    contrib = pd.DataFrame(index=P.index)
    for a in ["SPY", "TLT", "GLD"]:
        on = pos_frames[a]
        contrib[a] = 0.25 * (on * rets[a] + (1 - on) * cash)
    contrib["BIL"] = 0.25 * cash
    port = contrib.sum(axis=1)
    # turnover cost: when any gate flips
    flips = sum(pos_frames[a].diff().abs().fillna(0) for a in ["SPY", "TLT", "GLD"])
    port = port - 0.25 * flips * (cost_bps / 1e4)
    return port.dropna()


# ---------------------------------------------------------------------------
# BARBELL: blend safe base + convex sleeve, rebal daily (annual reset of weight)
# ---------------------------------------------------------------------------
def blend(safe_r, convex_r, w_convex):
    """Daily rebalanced blend (keeps the convex slice bounded each day -> 'you can
    only lose the convex slice' interpretation is approximate; daily rebal means the
    blend is continuously reset to target weight). Returns daily blend return."""
    df = pd.concat([safe_r.rename("safe"), convex_r.rename("cvx")], axis=1, sort=True).dropna()
    return (1 - w_convex) * df["safe"] + w_convex * df["cvx"]


def grow_to_target(daily_r, freq, start_cap=5000, monthly_contrib=500, target=70000,
                   n_paths=3000, max_years=15, block=20, haircut_ann=0.0,
                   gap_risk=False, gap_p=0.0, gap_size=-0.5):
    """Monte-Carlo: years to reach $target from start_cap + monthly contributions,
    using block-bootstrapped daily returns. Returns dict of stats incl median years,
    P(reach in <=N yr), and terminal-value distribution at fixed horizons."""
    r = pd.Series(daily_r).dropna().values
    n = len(r)
    hair_d = haircut_ann / freq
    r = r - hair_d
    days_max = int(max_years * freq)
    contrib_interval = int(freq / 12)
    years_to = []
    term = {1: [], 3: [], 5: []}
    horizons_d = {k: int(k * freq) for k in term}
    for _ in range(n_paths):
        # build a bootstrapped daily path
        path = np.empty(days_max)
        filled = 0
        while filled < days_max:
            start = RNG.integers(0, n)
            L = min(RNG.geometric(1.0 / block), days_max - filled)
            seg = np.arange(start, start + L) % n
            path[filled:filled + L] = r[seg]
            filled += L
        if gap_risk and gap_p > 0:
            hits = RNG.random(days_max) < (gap_p / freq)  # gap_p per YEAR
            path[hits] = path[hits] + gap_size
        cap = start_cap
        reached = None
        for d in range(days_max):
            cap *= (1 + path[d])
            if cap < 0:
                cap = 0.0
            if d % contrib_interval == 0 and d > 0:
                cap += monthly_contrib
            if reached is None and cap >= target:
                reached = (d + 1) / freq
            for k, hd in horizons_d.items():
                if d + 1 == hd:
                    term[k].append(cap)
        years_to.append(reached if reached is not None else np.nan)
    yt = np.array(years_to, float)
    reached_mask = ~np.isnan(yt)
    res = dict(
        median_years=float(np.nanmedian(yt)) if reached_mask.any() else None,
        p25_years=float(np.nanpercentile(yt, 25)) if reached_mask.any() else None,
        p75_years=float(np.nanpercentile(yt, 75)) if reached_mask.any() else None,
        P_reach_5yr=float(np.mean(yt <= 5)),
        P_reach_10yr=float(np.mean(yt <= 10)),
    )
    for k in term:
        arr = np.array(term[k], float)
        if len(arr):
            res[f"term_{k}yr"] = dict(
                median=float(np.median(arr)), p5=float(np.percentile(arr, 5)),
                p95=float(np.percentile(arr, 95)),
                P_2x=float(np.mean(arr >= 2 * start_cap)),
                P_5x=float(np.mean(arr >= 5 * start_cap)),
                P_half=float(np.mean(arr < 0.5 * start_cap)))
    return res


# ---------------------------------------------------------------------------
# A near-ruin drawdown means the LEFT TAIL IS NOT CAPPED -> fails the brutal bar
# even if historically +EV (the +EV was luck conditional on not having gapped to 0).
LEFT_TAIL_DD_LIMIT = -0.85


def dispro_score(m):
    """Disproportionate-positive score. REQUIRES BOTH:
      (1) +EV (mean_ann>0 AND CAGR>cash~2%), and
      (2) CAPPED LEFT TAIL (maxDD better than LEFT_TAIL_DD_LIMIT).
    Else score = NaN (rejected). Combines skew, tail ratio, omega, upside CAGR,
    penalized by drawdown depth."""
    if m is None:
        return float("nan"), "no-data"
    if m["mean_ann"] <= 0.02 or m["CAGR"] <= 0.02:
        return float("nan"), "REJECT: not +EV (<=cash)"
    if m["maxDD"] <= LEFT_TAIL_DD_LIMIT:
        return float("nan"), f"REJECT: left tail uncapped (maxDD {m['maxDD']*100:.0f}%)"
    # normalize-ish components
    skew = max(m["skew_m"] if not np.isnan(m["skew_m"]) else m["skew_d"], -1)
    tr = m["tail_ratio"] if not np.isnan(m["tail_ratio"]) else 1.0
    om = m["omega"] if not np.isnan(m["omega"]) else 1.0
    cagr = m["CAGR"]
    dd = abs(m["maxDD"])
    # score: reward skew, tail ratio>1, omega>1, CAGR; penalize deep DD mildly
    score = (max(skew, 0) * 1.0 + max(tr - 1, 0) * 1.5 + max(om - 1, 0) * 1.0
             + cagr * 2.0) / (1 + dd)
    return float(score), "+EV OK"


def fmt_m(name, m):
    if m is None:
        return f"{name:<34} (insufficient data)"
    return (f"{name:<34} CAGR {m['CAGR']*100:6.1f}%  Shp {m['Sharpe']:5.2f}  "
            f"maxDD {m['maxDD']*100:6.1f}%  skewM {m['skew_m']:5.2f}  "
            f"tailR {m['tail_ratio']:4.2f}  omega {m['omega']:4.2f}")


def main():
    px = load()
    out = {"window": {}, "candidates": {}, "contrasts": {}, "barbell": {}, "payoff": {}}
    print("=" * 110)
    print("DATA RANGES:")
    for c in px.columns:
        s = px[c].dropna()
        if len(s):
            print(f"  {c:9} {s.index[0].date()} .. {s.index[-1].date()}  n={s.count()}")
            out["window"][c] = [str(s.index[0].date()), str(s.index[-1].date()), int(s.count())]
    print("=" * 110)

    # ---- CANDIDATE CONVEX SLEEVES ----
    candidates = {}
    # (a) trend-timed BTC
    btc_tt, _ = trend_timed(px, "BTC-USD", 200, 20.0, "weekly")
    candidates["(a) BTC trend-timed SMA200"] = btc_tt
    # (b) trend-timed crypto basket BTC+ETH+SOL
    basket = trend_basket(px, ["BTC-USD", "ETH-USD", "SOL-USD"], 200, 20.0, "weekly")
    candidates["(b) Crypto basket trend-timed"] = basket
    # (c) leveraged trend-timed crypto 2x and 3x
    letf2, _ = letf_trend(px, "BTC-USD", 2.0, 200, 20.0, "weekly")
    letf3, _ = letf_trend(px, "BTC-USD", 3.0, 200, 20.0, "weekly")
    candidates["(c) BTC 2x trend-gated"] = letf2
    candidates["(c) BTC 3x trend-gated"] = letf3
    # (d) trend-following managed-futures style -- approximate with the safe-base TF
    #     diversified trend (use basket of SPY/TLT/GLD/DBC-less; we proxy with the
    #     crypto+equity trend blend). For a pure classic TF positive-skew proxy we use
    #     trend-timed GLD+TLT+SPY (cross-asset TS-momentum, crisis convex).
    tf_legs = []
    for a in ["SPY", "TLT", "GLD"]:
        st, _ = trend_timed(px, a, 200, 3.0, "weekly")
        tf_legs.append(st.rename(a))
    tf_md = pd.concat(tf_legs, axis=1).mean(axis=1).dropna()
    candidates["(d) Cross-asset TF (managed-fut)"] = tf_md

    print("\nCANDIDATE CONVEX SLEEVES (full history, net cost):")
    cand_metrics = {}
    for name, r in candidates.items():
        m = asym_metrics(r, freq=TD_CRYPTO if "BTC" in name or "basket" in name.lower() else TD_EQ)
        cand_metrics[name] = m
        sc, note = dispro_score(m)
        print(" ", fmt_m(name, m), f"| score {sc:6.2f} {note}")
        if m:
            mm = {k: v for k, v in m.items() if k != "daily"}
            mm["dispro_score"] = sc; mm["ev_note"] = note
            out["candidates"][name] = mm

    # ---- CONTRASTS (should FAIL the +EV / bounded-left-tail bar) ----
    contrasts = {}
    contrasts["X1 BTC buy-hold (no trend)"] = buyhold(px, "BTC-USD")
    contrasts["X2 naive 3x BTC LETF buy-hold"] = naive_letf_buyhold(px, "BTC-USD", 3.0)
    contrasts["X3 30%-OTM monthly call buying"] = otm_call_proxy(px, "BTC-USD")
    contrasts["X4 SOL buy-hold (lotto alt)"] = buyhold(px, "SOL-USD")
    print("\nCONTRASTS (prove the filter works -- expect REJECT or unbounded DD):")
    for name, r in contrasts.items():
        m = asym_metrics(r, freq=TD_CRYPTO)
        sc, note = dispro_score(m)
        print(" ", fmt_m(name, m), f"| score {sc:6.2f} {note}")
        if m:
            mm = {k: v for k, v in m.items() if k != "daily"}
            mm["dispro_score"] = sc; mm["ev_note"] = note
            out["contrasts"][name] = mm

    # ---- RECENT-REGIME CHECK (2022+) on the winner candidates ----
    print("\nRECENT-REGIME (2022-01+) -- is convexity a 2017/2021 artifact?")
    rec = {}
    btc_tt_r, _ = trend_timed(px, "BTC-USD", 200, 20.0, "weekly", start="2022-01-01")
    rec["(a) BTC trend-timed 2022+"] = btc_tt_r
    letf2_r, _ = letf_trend(px, "BTC-USD", 2.0, 200, 20.0, "weekly", start="2022-01-01")
    rec["(c) BTC 2x trend-gated 2022+"] = letf2_r
    rec["X1 BTC buy-hold 2022+"] = buyhold(px, "BTC-USD", start="2022-01-01")
    for name, r in rec.items():
        m = asym_metrics(r, freq=TD_CRYPTO)
        sc, note = dispro_score(m)
        print(" ", fmt_m(name, m), f"| score {sc:6.2f} {note}")
        if m:
            mm = {k: v for k, v in m.items() if k != "daily"}; mm["dispro_score"]=sc
            out.setdefault("recent", {})[name] = mm

    # ---- pick WINNER convex sleeve (best +EV dispro score among (a)-(d)) ----
    scored = {n: dispro_score(cand_metrics[n])[0] for n in candidates}
    scored = {n: s for n, s in scored.items() if not np.isnan(s)}
    winner = max(scored, key=scored.get)
    print(f"\n>>> WINNER convex sleeve: {winner}  (dispro {scored[winner]:.2f})")
    out["winner"] = winner
    winner_r = candidates[winner]

    # also keep the 2x as the AMPLIFIED option for the aggressive barbell
    amp_r = candidates["(c) BTC 2x trend-gated"]

    # ---- SAFE BASE ----
    base_r = safe_base(px)
    mb = asym_metrics(base_r, freq=TD_EQ)
    print("\nSAFE BASE (trend-overlaid all-weather SPY/TLT/GLD/BIL):")
    print(" ", fmt_m("safe base", mb))
    out["safe_base"] = {k: v for k, v in mb.items() if k != "daily"}

    # ---- BARBELL SWEEP ----
    # Use the 1x trend-timed BTC (winner if it is) as the primary convex slice and
    # also report a variant using 2x for max right tail. Blend with safe base.
    print("\n" + "=" * 110)
    print("BARBELL SWEEP  (safe base + convex sleeve, daily-rebalanced blend)")
    print("=" * 110)

    def sweep(convex_r, label):
        rows = []
        for w in [0.0, 0.05, 0.10, 0.20, 0.30, 0.50]:
            br = blend(base_r, convex_r, w)
            m = asym_metrics(br, freq=TD_EQ)
            # years to 70k via MC (fewer paths for the sweep)
            g = grow_to_target(br, TD_EQ, n_paths=1500, max_years=15,
                               haircut_ann=0.0)
            row = dict(w_convex=w, CAGR=m["CAGR"], maxDD=m["maxDD"], skew_m=m["skew_m"],
                       Sharpe=m["Sharpe"], tail_ratio=m["tail_ratio"],
                       median_years=g["median_years"], P_reach_5yr=g["P_reach_5yr"],
                       P_2x_3yr=g.get("term_3yr", {}).get("P_2x"),
                       P_ruin_proxy=g.get("term_3yr", {}).get("P_half"))
            rows.append(row)
            print(f"  {label} w={w*100:4.0f}%  CAGR {m['CAGR']*100:5.1f}%  "
                  f"maxDD {m['maxDD']*100:6.1f}%  skewM {m['skew_m']:5.2f}  "
                  f"Shp {m['Sharpe']:4.2f}  med-yrs->70k {str(g['median_years'])[:4]:>4}  "
                  f"P(2x,3y) {row['P_2x_3yr']:.2f}  P(<half,3y) {row['P_ruin_proxy']:.2f}")
        return rows

    out["barbell"]["winner_1x"] = sweep(winner_r, "1xBTC")
    out["barbell"]["amp_2x"] = sweep(amp_r, "2xBTC")

    # ---- HONEST PAYOFF DISTRIBUTION for the RECOMMENDED barbell ----
    # Recommendation logic: pick the weight that maximizes P(2x in 3yr) and CAGR
    # subject to P(ruin/<half) staying low (<~0.20) and maxDD bounded (~-40%).
    rec_w = 0.20
    rec_sleeve = winner_r
    print("\n" + "=" * 110)
    print(f"RECOMMENDED BARBELL: {rec_w*100:.0f}% [{winner}] + {(1-rec_w)*100:.0f}% safe base")
    print("HONEST PAYOFF DISTRIBUTION from $5k + $500/mo (haircut + gap risk on)")
    print("=" * 110)
    rec_blend = blend(base_r, rec_sleeve, rec_w)
    # haircut the crypto right tail: -10%/yr drift haircut on the BLEND's crypto portion
    # approximate by haircutting the whole blend by rec_w*0.10
    g_base = grow_to_target(rec_blend, TD_EQ, n_paths=5000, max_years=15,
                            haircut_ann=0.0, gap_risk=True, gap_p=0.5*rec_w, gap_size=-0.4)
    g_hair = grow_to_target(rec_blend, TD_EQ, n_paths=5000, max_years=15,
                            haircut_ann=rec_w * 0.12, gap_risk=True,
                            gap_p=0.5 * rec_w, gap_size=-0.4)
    out["payoff"]["recommended_weight"] = rec_w
    out["payoff"]["winner"] = winner
    out["payoff"]["no_haircut"] = g_base
    out["payoff"]["haircut"] = g_hair

    # LUMP-SUM payoff (NO contributions) to isolate the CONVEXITY asymmetry cleanly
    # -- P(2x)/P(5x) here reflect MARKET return only, not contribution inflows.
    print("\n  LUMP-SUM $5k, NO contributions (isolates convexity; haircut+gap on):")
    g_lump = grow_to_target(rec_blend, TD_EQ, start_cap=5000, monthly_contrib=0,
                            target=70000, n_paths=5000, max_years=15,
                            haircut_ann=rec_w * 0.12, gap_risk=True,
                            gap_p=0.5 * rec_w, gap_size=-0.4)
    out["payoff"]["lump_sum_haircut"] = g_lump
    for k in [1, 3, 5]:
        t = g_lump.get(f"term_{k}yr")
        if t:
            print(f"    {k}yr: median ${t['median']:,.0f}  p5 ${t['p5']:,.0f}  "
                  f"p95 ${t['p95']:,.0f}  P(2x){t['P_2x']:.2f}  P(5x){t['P_5x']:.2f}  "
                  f"P(<half){t['P_half']:.2f}")
    # also lump-sum for the PURE convex sleeve alone (the disproportionate payoff)
    print("\n  LUMP-SUM $5k in PURE convex sleeve alone (max asymmetry, haircut on):")
    g_pure = grow_to_target(rec_sleeve, TD_CRYPTO, start_cap=5000, monthly_contrib=0,
                            target=70000, n_paths=5000, max_years=15,
                            haircut_ann=0.20, gap_risk=True, gap_p=0.5, gap_size=-0.4)
    out["payoff"]["lump_sum_pure_convex"] = g_pure
    for k in [1, 3, 5]:
        t = g_pure.get(f"term_{k}yr")
        if t:
            print(f"    {k}yr: median ${t['median']:,.0f}  p5 ${t['p5']:,.0f}  "
                  f"p95 ${t['p95']:,.0f}  P(2x){t['P_2x']:.2f}  P(5x){t['P_5x']:.2f}  "
                  f"P(<half){t['P_half']:.2f}")
    for label, g in [("NO-haircut", g_base), ("HAIRCUT(-12%/yr on cvx)", g_hair)]:
        print(f"\n  [{label}]  median yrs->70k = {g['median_years']}  "
              f"P(reach 5yr)={g['P_reach_5yr']:.2f}  P(reach 10yr)={g['P_reach_10yr']:.2f}")
        for k in [1, 3, 5]:
            t = g.get(f"term_{k}yr")
            if t:
                print(f"    {k}yr: median ${t['median']:,.0f}  p5 ${t['p5']:,.0f}  "
                      f"p95 ${t['p95']:,.0f}  P(2x){t['P_2x']:.2f}  P(5x){t['P_5x']:.2f}  "
                      f"P(<half){t['P_half']:.2f}")

    with open("/tmp/convex_data/results.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nsaved /tmp/convex_data/results.json")
    return out


if __name__ == "__main__":
    main()
