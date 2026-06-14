"""Do stocks predict BTC? Cross-asset lead-lag, Granger, overnight-gap test, backtest.

Reads staged CSVs from /tmp/spbtc_data. Prints a structured report consumed to build
STOCKS_PREDICT_BTC.md. No look-ahead: signal at t, position at t+1.
"""
import warnings
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests

warnings.simplefilter("ignore")
DATA = "/tmp/spbtc_data"

CANDIDATES = [
    "MSTR", "COIN", "RIOT", "MARA", "CLSK", "IBIT", "GBTC",  # crypto proxies
    "QQQ", "SOXX", "ARKK", "SPY", "IWM",                      # tech/risk
    "UUP", "TLT", "GLD", "HYG", "^VIX",                       # macro
]
PROXY = {"MSTR", "COIN", "RIOT", "MARA", "CLSK", "IBIT", "GBTC"}


def newey_corr_test(x, y, nlags=5):
    """Pearson corr + HAC-robust t via OLS of y~x with Newey-West SE.
    Returns (corr, n, t_hac, p_hac)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    n = len(x)
    if n < 30:
        return np.nan, n, np.nan, np.nan
    r = np.corrcoef(x, y)[0, 1]
    import statsmodels.api as sm
    X = sm.add_constant(x)
    res = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": nlags})
    return r, n, res.tvalues[1], res.pvalues[1]


def load_daily():
    df = pd.read_csv(f"{DATA}/daily_close.csv", index_col=0, parse_dates=True)
    df = df.loc["2014-01-01":]
    ret = np.log(df).diff()
    return df, ret


def load_hourly():
    df = pd.read_csv(f"{DATA}/hourly_close.csv", index_col=0)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()
    # Equities stamp on :30, BTC/VIX on :00 -> different grids, zero overlap.
    # Snap everything to a common 1h grid (bin label = last obs in the hour),
    # then forward-fill within equity session days only for the candidates.
    grid = df.resample("1h").last()
    # restrict to US equity session hours (13:00-21:00 UTC covers 09:30-16:00 ET both DST)
    grid = grid[(grid.index.hour >= 13) & (grid.index.hour <= 21)]
    grid = grid.ffill(limit=2)  # bridge :30 vs :00 stamping within a session
    ret = np.log(grid).diff()
    # blank the first intraday bar of each calendar day to drop the overnight gap
    day = pd.Series(grid.index.normalize(), index=grid.index)
    first_of_day = day != day.shift(1)
    ret.loc[first_of_day.values] = np.nan
    return grid, ret


# ---------------------------------------------------------------------------
def leadlag_matrix(ret, btc="BTC-USD", label="DAILY", recent_n=None):
    print(f"\n{'='*78}\nLEAD-LAG MATRIX [{label}]  (returns, contemporaneous + both lead dirs)")
    if recent_n:
        ret = ret.iloc[-recent_n:]
    print(f"window: {ret.index.min()} -> {ret.index.max()}  (rows={len(ret)})")
    b = ret[btc]
    print(f"\n{'cand':<8} {'corr_t,t':>9} {'p':>7} | "
          f"{'cand_t->BTC_t+1':>16} {'p':>7} | {'BTC_t->cand_t+1':>16} {'p':>7} | who")
    rows = []
    for c in CANDIDATES:
        if c not in ret.columns:
            continue
        s = ret[c]
        # contemporaneous
        r0, n0, _, p0 = newey_corr_test(s, b)
        # cand_t -> BTC_t+1
        r_fwd, _, _, p_fwd = newey_corr_test(s.iloc[:-1].values, b.shift(-1).iloc[:-1].values)
        # BTC_t -> cand_t+1
        r_rev, _, _, p_rev = newey_corr_test(b.iloc[:-1].values, s.shift(-1).iloc[:-1].values)
        who = ""
        sig = 0.01  # strict bar for multiple testing
        if p_fwd < sig and p_rev >= sig:
            who = "CAND leads BTC"
        elif p_rev < sig and p_fwd >= sig:
            who = "BTC leads cand"
        elif p_fwd < sig and p_rev < sig:
            who = "bidirectional"
        else:
            who = "neither"
        print(f"{c:<8} {r0:>9.3f} {p0:>7.3f} | {r_fwd:>16.3f} {p_fwd:>7.3f} | "
              f"{r_rev:>16.3f} {p_rev:>7.3f} | {who}")
        rows.append(dict(cand=c, corr0=r0, p0=p0, fwd=r_fwd, p_fwd=p_fwd,
                         rev=r_rev, p_rev=p_rev, who=who, n=n0))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def granger(ret, btc="BTC-USD", maxlag=3, label="FULL"):
    print(f"\n{'='*78}\nGRANGER CAUSALITY cand -> BTC [{label}]  (controls BTC own lags, maxlag={maxlag})")
    print(f"window {ret.index.min()} -> {ret.index.max()} rows={len(ret)}")
    b = ret[btc]
    print(f"{'cand':<8} {'bestlag':>7} {'F':>8} {'p':>9} {'sig@0.01?':>10}")
    out = []
    for c in CANDIDATES:
        if c not in ret.columns:
            continue
        d = pd.concat([b, ret[c]], axis=1).dropna()  # col0=BTC(effect), col1=cand(cause)
        if len(d) < 100:
            continue
        try:
            res = grangercausalitytests(d.values, maxlag=maxlag, verbose=False)
            # pick min p across lags
            best = min(res.items(), key=lambda kv: kv[1][0]["ssr_ftest"][1])
            lag, (stat, _) = best
            F, p = stat["ssr_ftest"][0], stat["ssr_ftest"][1]
        except Exception as e:
            F, p, lag = np.nan, np.nan, -1
        flag = "YES" if p < 0.01 else ""
        print(f"{c:<8} {lag:>7} {F:>8.2f} {p:>9.4f} {flag:>10}")
        out.append(dict(cand=c, lag=lag, F=F, p=p))
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
def overnight_gap_test():
    """THE decisive non-contemporaneous test.
    Equity SESSION return (open->close, ~13:30-21:00 UTC) predicts BTC's OVERNIGHT
    return measured while equities are CLOSED (equity close -> next equity open).
    Uses hourly data. NY session ~09:30-16:00 ET.
    """
    print(f"\n{'='*78}\nOVERNIGHT-GAP TEST  (equity session ret -> BTC overnight ret, equities CLOSED)")
    df = pd.read_csv(f"{DATA}/hourly_close.csv", index_col=0)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()
    # BTC trades 24/7 on the :00 grid. Build a continuous ffilled hourly BTC series.
    btc = df["BTC-USD"].dropna()
    btc_h = btc.resample("1h").last().ffill()

    def btc_at(ts):
        # value of BTC at the hour bin containing ts
        key = ts.floor("1h")
        try:
            return btc_h.asof(key)
        except Exception:
            return np.nan

    # Equity session per ET day: open=first SPY bar (09:30 ET), close=last SPY bar (15:30 ET).
    et = df.index.tz_convert("America/New_York")
    df = df.copy()
    df["date"] = et.date
    df["ehour"] = et.hour
    sessions = []
    for d, g in df.groupby("date"):
        g = g.sort_index()
        eq = g[(g["ehour"] >= 9) & (g["ehour"] <= 16) & g["SPY"].notna()]
        if len(eq) < 3:
            continue
        sessions.append((d, eq.index[0], eq.index[-1]))
    sess = pd.DataFrame(sessions, columns=["date", "t_open", "t_close"]).sort_values("t_open")

    recs = []
    for i in range(len(sess) - 1):
        to, tc = sess.iloc[i].t_open, sess.iloc[i].t_close
        to_next = sess.iloc[i + 1].t_open
        row = dict(date=sess.iloc[i].date)
        # BTC overnight: session close (16:00 ET) -> next session open (09:30 ET), equities CLOSED
        bc, bo_next, bo = btc_at(tc), btc_at(to_next), btc_at(to)
        if not (np.isfinite(bc) and np.isfinite(bo_next) and bc > 0):
            continue
        row["btc_overnight"] = np.log(bo_next / bc)
        if np.isfinite(bo) and bo > 0:
            row["btc_session"] = np.log(bc / bo)
        # equity session returns (open SPY bar -> close SPY bar)
        gday = df[df["date"] == sess.iloc[i].date].sort_index()
        for c in CANDIDATES:
            if c not in df.columns:
                continue
            ser = gday[c].dropna()
            if len(ser) >= 2 and ser.iloc[0] > 0:
                row[f"{c}_session"] = np.log(ser.iloc[-1] / ser.iloc[0])
        recs.append(row)
    R = pd.DataFrame(recs).set_index("date")
    print(f"sessions usable: {len(R)}  ({R.index.min()} -> {R.index.max()})")

    print(f"\n{'cand':<8} {'sess_ret->BTC_overnight':>22} {'p(HAC)':>8} | "
          f"{'sess_ret->BTC_session(contemp)':>30} {'p':>7}")
    out = []
    for c in CANDIDATES:
        col = f"{c}_session"
        if col not in R.columns:
            continue
        # predictive: equity session ret -> BTC OVERNIGHT (non-contemp, equities closed)
        r_p, n_p, _, p_p = newey_corr_test(R[col].values, R["btc_overnight"].values)
        # contemporaneous: equity session ret vs BTC during same session
        r_c, _, _, p_c = newey_corr_test(R[col].values, R["btc_session"].values)
        out.append(dict(cand=c, r_overnight=r_p, p_overnight=p_p,
                        r_contemp=r_c, p_contemp=p_c, n=n_p))
        print(f"{c:<8} {r_p:>22.3f} {p_p:>8.3f} | {r_c:>30.3f} {p_c:>7.3f}")
    print("\nINTERPRETATION: large r_contemp + ~0 r_overnight  => contemporaneous risk-on,"
          " NOT a lead.\n  Only a significant r_overnight (equities closed) is a genuine lead.")
    return pd.DataFrame(out), R


# ---------------------------------------------------------------------------
def backtest_overnight(R, signal_cand, btc_col="btc_overnight"):
    """Trade BTC overnight on sign of today's equity session return. Net of costs.
    OOS = last 40%. Compare vs buy-hold-overnight.
    """
    col = f"{signal_cand}_session"
    d = R[[col, btc_col]].dropna()
    sig = np.sign(d[col].values)
    fwd = d[btc_col].values
    n = len(d)
    split = int(n * 0.6)
    # cost: trading BTC overnight, round-trip ~ assume 10 bps each side when position flips
    COST = 0.0010  # 10bps per change
    def run(s, f):
        pos = s.copy()
        flips = np.abs(np.diff(np.concatenate([[0], pos])))
        gross = pos * f
        net = gross - flips * COST
        return net
    net = run(sig, fwd)
    is_net, oos_net = net[:split], net[split:]
    bh_oos = fwd[split:]
    def stats_(x):
        if len(x) == 0 or x.std() == 0:
            return 0, 0
        sh = x.mean() / x.std() * np.sqrt(252)
        return x.sum(), sh
    s_oos, sh_oos = stats_(oos_net)
    bh_sum, bh_sh = stats_(bh_oos)
    return dict(cand=signal_cand, n=n, oos_cumret=s_oos, oos_sharpe=sh_oos,
                bh_oos_cumret=bh_sum, bh_oos_sharpe=bh_sh)


# ---------------------------------------------------------------------------
def daily_backtest(ret, signal_cand, btc="BTC-USD", recent_split=0.6):
    """Long/flat daily BTC: long when signal_cand return_t > 0, else flat (cash 0).
    Position at t+1. Net of costs. OOS = last 40%. Compare buy-hold and 200d trend.
    """
    df = pd.read_csv(f"{DATA}/daily_close.csv", index_col=0, parse_dates=True).loc["2014-01-01":]
    px = df[btc]
    sma200 = px.rolling(200).mean()
    r = ret[[signal_cand, btc]].dropna()
    sig = (r[signal_cand].shift(1) > 0).astype(float)  # signal at t-1 -> position at t
    btc_r = r[btc]
    COST = 0.0010
    pos = sig.values
    flips = np.abs(np.diff(np.concatenate([[0.0], pos])))
    net = pos * btc_r.values - flips * COST
    net = pd.Series(net, index=r.index)
    # 200d trend rule
    trend_sig = (px.shift(1) > sma200.shift(1)).reindex(r.index).fillna(False).astype(float)
    tflips = np.abs(np.diff(np.concatenate([[0.0], trend_sig.values])))
    trend_net = pd.Series(trend_sig.values * btc_r.values - tflips * COST, index=r.index)
    bh = btc_r.copy()
    n = len(r)
    split = int(n * recent_split)
    def sh(x):
        x = x.dropna()
        return x.mean() / x.std() * np.sqrt(365) if x.std() > 0 else 0
    def cagr(x):
        x = x.dropna()
        yrs = len(x) / 365
        return np.exp(x.sum()) ** (1 / yrs) - 1 if yrs > 0 else 0
    seg = lambda x: x.iloc[split:]
    return dict(
        cand=signal_cand,
        oos_sharpe=sh(seg(net)), oos_cagr=cagr(seg(net)),
        bh_oos_sharpe=sh(seg(bh)), bh_oos_cagr=cagr(seg(bh)),
        trend_oos_sharpe=sh(seg(trend_net)), trend_oos_cagr=cagr(seg(trend_net)),
        full_sharpe=sh(net),
    )


if __name__ == "__main__":
    px_d, ret_d = load_daily()
    print("BTC daily span:", ret_d["BTC-USD"].dropna().index.min(),
          "->", ret_d["BTC-USD"].dropna().index.max())

    # 1+2. Lead-lag matrices: full daily, recent daily (last 504 ~ 2yr), recent (2022 regime)
    m_full = leadlag_matrix(ret_d, label="DAILY FULL")
    m_rec = leadlag_matrix(ret_d, label="DAILY RECENT ~2yr", recent_n=504)
    # 2021-2022 high-corr regime
    ret_2122 = ret_d.loc["2021-01-01":"2022-12-31"]
    m_2122 = leadlag_matrix(ret_2122, label="DAILY 2021-2022 regime")

    # hourly lead-lag
    px_h, ret_h = load_hourly()
    m_h = leadlag_matrix(ret_h, label="HOURLY ~730d")

    # OVERLAP-ARTIFACT CHECK: equity bars stamp :30, BTC :00 -> BTC_t+1 overlaps eq_t by 30min.
    # A genuine lead survives at lag-2 (fully disjoint). Compare lag1 vs lag2.
    print(f"\n{'='*78}\nHOURLY OVERLAP-ARTIFACT CHECK: cand_t -> BTC_t+1 vs BTC_t+2 (disjoint)")
    bh = ret_h["BTC-USD"]
    print(f"{'cand':<8} {'r(lag1)':>8} {'p1':>7} {'r(lag2 disjoint)':>17} {'p2':>7}")
    for c in CANDIDATES:
        if c not in ret_h.columns:
            continue
        s = ret_h[c]
        r1, _, _, p1 = newey_corr_test(s.iloc[:-1].values, bh.shift(-1).iloc[:-1].values)
        r2, _, _, p2 = newey_corr_test(s.iloc[:-2].values, bh.shift(-2).iloc[:-2].values)
        print(f"{c:<8} {r1:>8.3f} {p1:>7.3f} {r2:>17.3f} {p2:>7.3f}")
    print("  -> if lag1 large but lag2 ~0, the 'lead' is the 30-min bar-overlap artifact, "
          "NOT a tradable lead.")

    # 3. Granger full + recent
    g_full = granger(ret_d, label="DAILY FULL")
    g_rec = granger(ret_d.iloc[-504:], label="DAILY RECENT ~2yr")
    g_2122 = granger(ret_2122, label="DAILY 2021-2022")

    # 4. Overnight-gap test
    og, R = overnight_gap_test()

    # 5. Backtests
    print(f"\n{'='*78}\nBACKTEST: daily long/flat BTC on cand_t>0 signal (net 10bps), OOS=last40%")
    print(f"{'cand':<8} {'OOS_Sharpe':>10} {'OOS_CAGR':>9} | {'BH_Sh':>7} {'BH_CAGR':>8} | "
          f"{'Trend_Sh':>8} {'Trend_CAGR':>10}")
    bt_rows = []
    for c in CANDIDATES:
        if c not in ret_d.columns:
            continue
        try:
            b = daily_backtest(ret_d, c)
            bt_rows.append(b)
            print(f"{c:<8} {b['oos_sharpe']:>10.2f} {b['oos_cagr']*100:>8.1f}% | "
                  f"{b['bh_oos_sharpe']:>7.2f} {b['bh_oos_cagr']*100:>7.1f}% | "
                  f"{b['trend_oos_sharpe']:>8.2f} {b['trend_oos_cagr']*100:>9.1f}%")
        except Exception as e:
            print(f"{c}: bt failed {e}")

    print(f"\n{'='*78}\nBACKTEST: overnight BTC on sign(equity session ret) (net 10bps), OOS=last40%")
    print(f"{'cand':<8} {'OOS_cumret':>10} {'OOS_Sharpe':>10} | {'BH_overnight_cum':>16} {'BH_Sh':>7}")
    for c in CANDIDATES:
        col = f"{c}_session"
        if col not in R.columns:
            continue
        b = backtest_overnight(R, c)
        print(f"{c:<8} {b['oos_cumret']*100:>9.1f}% {b['oos_sharpe']:>10.2f} | "
              f"{b['bh_oos_cumret']*100:>15.1f}% {b['bh_oos_sharpe']:>7.2f}")

    print("\nDONE")
