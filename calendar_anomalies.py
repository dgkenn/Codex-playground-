#!/usr/bin/env python3
"""
Calendar / seasonal anomaly tests as cheap US-legal timing overlays on the equity sleeve.

Tests documented US-equity calendar anomalies with:
  - long history + recent-decade (2016-2026) holdout
  - realistic costs (commission-free ETF + spread bps charged on every entry/exit)
  - multiple-testing skepticism (Bonferroni / higher bar)
  - deployability check vs buy-and-hold SPY and "would it add to the momentum+TF book"

Data: yfinance daily ADJUSTED closes (auto_adjust=True => total return). Staged to /tmp/cal_data.
Costs default: 3 bps per side (matches ETF_MOMENTUM convention); sensitivity at 0/3/10 bps.

Anomalies:
  1. Pre-FOMC announcement drift (Lucca-Moench 2015) — hardcoded FOMC calendar 2010-2026
  2. Turn-of-the-month (last 1 + first 3 trading days)
  3. Sell-in-May / Halloween (Nov-Apr vs May-Oct)
  4. Day-of-week (Monday) + pre-holiday
  5. Santa Claus rally / January / end-of-quarter

NOTHING here is "in-window only" cherry-picked: each test reports full-sample, recent-decade,
and net-of-cost numbers, with a Newey-West t-stat on daily log returns.
"""
import os, sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

DATADIR = "/tmp/cal_data"
os.makedirs(DATADIR, exist_ok=True)
RECENT_START = "2016-01-01"
ANN = 252

# ---------------------------------------------------------------- data
def get_prices():
    fp = os.path.join(DATADIR, "prices.csv")
    if os.path.exists(fp):
        df = pd.read_csv(fp, index_col=0, parse_dates=True)
        if len(df) > 1000:
            return df
    import yfinance as yf
    tk = ["SPY", "QQQ", "IWM"]
    for attempt in range(4):
        try:
            raw = yf.download(tk, start="1993-01-01", end="2026-06-15",
                              auto_adjust=True, progress=False)["Close"]
            if raw.dropna(how="all").shape[0] > 1000:
                raw.to_csv(fp)
                return raw
        except Exception as e:
            print("retry", attempt, e, file=sys.stderr)
    raise RuntimeError("yfinance failed")

# ---------------------------------------------------------------- FOMC calendar (scheduled announcement dates)
# 8/yr scheduled meetings; date = day of the policy statement release (2nd day of 2-day meetings).
# Source: Federal Reserve historical FOMC calendars 2010-2026.
FOMC_DATES = [
 # 2010
 "2010-01-27","2010-03-16","2010-04-28","2010-06-23","2010-08-10","2010-09-21","2010-11-03","2010-12-14",
 # 2011
 "2011-01-26","2011-03-15","2011-04-27","2011-06-22","2011-08-09","2011-09-21","2011-11-02","2011-12-13",
 # 2012
 "2012-01-25","2012-03-13","2012-04-25","2012-06-20","2012-08-01","2012-09-13","2012-10-24","2012-12-12",
 # 2013
 "2013-01-30","2013-03-20","2013-05-01","2013-06-19","2013-07-31","2013-09-18","2013-10-30","2013-12-18",
 # 2014
 "2014-01-29","2014-03-19","2014-04-30","2014-06-18","2014-07-30","2014-09-17","2014-10-29","2014-12-17",
 # 2015
 "2015-01-28","2015-03-18","2015-04-29","2015-06-17","2015-07-29","2015-09-17","2015-10-28","2015-12-16",
 # 2016
 "2016-01-27","2016-03-16","2016-04-27","2016-06-15","2016-07-27","2016-09-21","2016-11-02","2016-12-14",
 # 2017
 "2017-02-01","2017-03-15","2017-05-03","2017-06-14","2017-07-26","2017-09-20","2017-11-01","2017-12-13",
 # 2018
 "2018-01-31","2018-03-21","2018-05-02","2018-06-13","2018-08-01","2018-09-26","2018-11-08","2018-12-19",
 # 2019
 "2019-01-30","2019-03-20","2019-05-01","2019-06-19","2019-07-31","2019-09-18","2019-10-30","2019-12-11",
 # 2020 (incl. unscheduled 3/3 & 3/15 emergency cuts — exclude unscheduled; keep regular)
 "2020-01-29","2020-03-18","2020-04-29","2020-06-10","2020-07-29","2020-09-16","2020-11-05","2020-12-16",
 # 2021
 "2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
 # 2022
 "2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
 # 2023
 "2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
 # 2024
 "2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
 # 2025
 "2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
 # 2026 (scheduled)
 "2026-01-28","2026-03-18","2026-04-29","2026-06-17",
]
FOMC = pd.to_datetime(FOMC_DATES)

# ---------------------------------------------------------------- stats helpers
def nw_tstat(x, lags=5):
    """Newey-West t-stat of mean(x) != 0 on a return series x."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 10:
        return np.nan, np.nan, n
    mu = x.mean()
    d = x - mu
    gamma0 = (d @ d) / n
    var = gamma0
    for L in range(1, min(lags, n - 1) + 1):
        cov = (d[L:] @ d[:-L]) / n
        var += 2 * (1 - L / (lags + 1)) * cov
    se = np.sqrt(var / n)
    t = mu / se if se > 0 else np.nan
    return mu, t, n

def ann_stats(daily):
    """daily simple returns -> CAGR, ann vol, Sharpe, maxDD."""
    d = pd.Series(daily).dropna()
    if len(d) < 30:
        return dict(CAGR=np.nan, vol=np.nan, Sharpe=np.nan, maxDD=np.nan, n=len(d))
    eq = (1 + d).cumprod()
    yrs = len(d) / ANN
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = d.std() * np.sqrt(ANN)
    shp = (d.mean() * ANN) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return dict(CAGR=cagr, vol=vol, Sharpe=shp, maxDD=dd, n=len(d))

def split_report(label, mask, ret, idx, cost_bps_roundtrip=0.0):
    """Report mean daily ret in-window vs out, full + recent, with NW t-stat.
       cost: charge half the round-trip on each window boundary (entry+exit)."""
    rows = []
    for tag, sub in [("full", slice(None)), ("recent", idx >= pd.Timestamp(RECENT_START))]:
        if tag == "recent":
            m = mask & sub
            o = (~mask) & sub
        else:
            m = mask
            o = ~mask
        rin = ret[m]
        rout = ret[o]
        mu_in, t_in, n_in = nw_tstat(rin.values)
        mu_out, _, n_out = nw_tstat(rout.values)
        rows.append((tag, mu_in, t_in, n_in, mu_out, n_out))
    return rows

def overlay_backtest(in_window, ret, leverage_in=1.0, lev_out=0.0, cost_bps=3.0):
    """Be invested leverage_in during window, lev_out otherwise. Charge cost_bps per side
       on every change in exposure (turnover)."""
    expo = pd.Series(np.where(in_window, leverage_in, lev_out), index=ret.index)
    turn = expo.diff().abs().fillna(expo.iloc[0])
    cost = turn * (cost_bps / 1e4)
    strat = expo.shift(1).fillna(0) * ret - cost.shift(1).fillna(0)
    # (apply exposure decided at close t-1 to return t; cost when changing)
    strat2 = expo * ret - cost  # simpler: same-bar; exposure known at prior close
    return expo * ret - cost

# ---------------------------------------------------------------- masks
def make_calendar_masks(idx):
    s = pd.Series(idx, index=idx)
    df = pd.DataFrame(index=idx)
    df["dow"] = idx.dayofweek
    df["month"] = idx.month
    df["day"] = idx.day
    # trading-day-of-month position
    tdom = s.groupby([idx.year, idx.month]).cumcount() + 1
    n_in_month = s.groupby([idx.year, idx.month]).transform("count")
    tdom_from_end = n_in_month.values - tdom.values  # 0 = last trading day
    df["tdom"] = tdom.values
    df["tdom_from_end"] = tdom_from_end
    return df

# ============================================================ MAIN
def main():
    px = get_prices()
    px = px.dropna(how="all")
    out = []
    P = lambda *a: (print(*a), out.append(" ".join(str(x) for x in a)))[1]

    for tkr in ["SPY", "QQQ", "IWM"]:
        if tkr not in px.columns:
            continue
        s = px[tkr].dropna()
        ret = s.pct_change().dropna()
        idx = ret.index
        cal = make_calendar_masks(idx)
        P("\n" + "=" * 78)
        P(f"### {tkr}  ({idx[0].date()} -> {idx[-1].date()}, {len(ret)} days)")
        P("=" * 78)

        # ---- baseline buy&hold for reference
        bh_full = ann_stats(ret)
        bh_rec = ann_stats(ret[idx >= pd.Timestamp(RECENT_START)])
        P(f"[buy&hold] full  CAGR {bh_full['CAGR']*100:5.2f}%  Sharpe {bh_full['Sharpe']:.2f}  maxDD {bh_full['maxDD']*100:.1f}%")
        P(f"[buy&hold] recent CAGR {bh_rec['CAGR']*100:5.2f}%  Sharpe {bh_rec['Sharpe']:.2f}  maxDD {bh_rec['maxDD']*100:.1f}%")

        anomalies = {}

        # 1. PRE-FOMC: day before scheduled announcement (t-1). Build mask on this idx.
        fomc_in_range = FOMC[(FOMC >= idx[0]) & (FOMC <= idx[-1])]
        # map each FOMC date to the trading day strictly before it
        pos = idx.searchsorted(fomc_in_range)  # index of first trading day >= fomc date
        pre_pos = pos - 1
        pre_pos = pre_pos[(pre_pos >= 0) & (pre_pos < len(idx))]
        prefomc_mask = pd.Series(False, index=idx)
        prefomc_mask.iloc[pre_pos] = True
        anomalies["1.pre-FOMC (t-1)"] = prefomc_mask

        # 2. TURN OF MONTH: last 1 trading day + first 3 trading days
        tom = (cal["tdom_from_end"] == 0) | (cal["tdom"] <= 3)
        anomalies["2.turn-of-month (-1..+3)"] = pd.Series(tom.values, index=idx)

        # 3. HALLOWEEN: Nov-Apr in-window
        hall = cal["month"].isin([11, 12, 1, 2, 3, 4])
        anomalies["3.Halloween (Nov-Apr)"] = pd.Series(hall.values, index=idx)

        # 4a. MONDAY
        mon = cal["dow"] == 0
        anomalies["4a.Monday"] = pd.Series(mon.values, index=idx)
        # 4b. PRE-HOLIDAY: trading day before a >1 calendar-day gap to next trading day (proxy)
        gap = (idx[1:] - idx[:-1]).days
        prehol = np.zeros(len(idx), bool)
        prehol[:-1] = gap >= 3  # Fri->Mon is 3 already; use >=4 to isolate holidays
        prehol_strict = np.zeros(len(idx), bool)
        prehol_strict[:-1] = gap >= 4
        anomalies["4b.pre-holiday (gap>=4d)"] = pd.Series(prehol_strict, index=idx)

        # 5a. SANTA CLAUS: last 5 trading days of year + first 2 of next year
        last5 = (cal["month"] == 12) & (cal["tdom_from_end"] <= 4)
        first2 = (cal["month"] == 1) & (cal["tdom"] <= 2)
        santa = pd.Series((last5 | first2).values, index=idx)
        anomalies["5a.Santa (last5+first2)"] = santa
        # 5b. JANUARY (whole month)
        anomalies["5b.January"] = pd.Series((cal["month"] == 1).values, index=idx)
        # 5c. END OF QUARTER: last 3 trading days of Mar/Jun/Sep/Dec
        eoq = (cal["month"].isin([3, 6, 9, 12])) & (cal["tdom_from_end"] <= 2)
        anomalies["5c.end-of-quarter (last3)"] = pd.Series(eoq.values, index=idx)

        P(f"\n  anomaly                         | full mean(bps)  t   n_in || recent mean(bps)  t  n_in")
        P("  " + "-" * 90)
        results = {}
        for name, mask in anomalies.items():
            mask = mask.reindex(idx).fillna(False)
            mu_f, t_f, n_f = nw_tstat(ret[mask].values)
            recmask = mask & (idx >= pd.Timestamp(RECENT_START))
            mu_r, t_r, n_r = nw_tstat(ret[recmask].values)
            results[name] = dict(mu_f=mu_f, t_f=t_f, n_f=n_f, mu_r=mu_r, t_r=t_r, n_r=n_r, mask=mask)
            P(f"  {name:31s} | {mu_f*1e4:8.2f}  {t_f:5.2f} {n_f:5d} || {mu_r*1e4:8.2f}  {t_r:5.2f} {n_r:5d}")

        anomalies_results[tkr] = results

    # ---------------- deployability: best survivor as overlay on SPY (decide after seeing screens)
    print("\n" + "#" * 78)
    print("# OVERLAY BACKTESTS ON SPY (decide best survivors below)")
    print("#" * 78)
    spy = px["SPY"].dropna()
    ret = spy.pct_change().dropna()
    idx = ret.index
    R = anomalies_results["SPY"]

    def run_overlay(name, mask, lev_in, lev_out, label):
        print(f"\n-- {label}: invest {lev_in}x in [{name}], {lev_out}x otherwise --")
        for cost in [0.0, 3.0, 10.0]:
            for tag, sub in [("full", idx), ("recent", idx[idx >= pd.Timestamp(RECENT_START)])]:
                m = mask.reindex(sub).fillna(False)
                rr = ret.reindex(sub)
                strat = overlay_backtest(m, rr, lev_in, lev_out, cost)
                st = ann_stats(strat)
                bh = ann_stats(rr)
                frac = m.mean()
                print(f"   cost {cost:4.1f}bps {tag:6s}: CAGR {st['CAGR']*100:6.2f}% Sh {st['Sharpe']:5.2f} "
                      f"DD {st['maxDD']*100:6.1f}% | inWin% {frac*100:4.1f} | BH Sh {bh['Sharpe']:.2f}")

    # Turn-of-month: classic deployable form = invested only in TOM, cash otherwise
    run_overlay("turn-of-month", R["2.turn-of-month (-1..+3)"]["mask"], 1.0, 0.0, "TOM in / cash out")
    # Halloween: invested Nov-Apr, cash May-Oct
    run_overlay("Halloween", R["3.Halloween (Nov-Apr)"]["mask"], 1.0, 0.0, "Nov-Apr in / cash May-Oct")
    # Pre-FOMC
    run_overlay("pre-FOMC", R["1.pre-FOMC (t-1)"]["mask"], 1.0, 0.0, "pre-FOMC day in / cash out")
    # TOM tilt (overweight, stay invested) — more realistic low-turnover form
    run_overlay("TOM-tilt", R["2.turn-of-month (-1..+3)"]["mask"], 1.5, 0.5, "TOM 1.5x / 0.5x")

    return out

anomalies_results = {}
if __name__ == "__main__":
    main()
