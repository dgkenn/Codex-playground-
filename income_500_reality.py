#!/usr/bin/env python3
"""
INCOME_500_REALITY — the brutally honest capital-vs-return / ruin / withdrawal
reality check for the operator goal: "make ~$500/month ($6,000/yr) trading from a
SMALL bankroll."

This script does NOT re-derive any strategy. It RECONSTRUCTS the four validated
project return series from yfinance (same logic as the committed engines:
static_allocation.py PP, etf_momentum.py + trend_following.py active book,
btc_trend_timing.py BTC SMA200-weekly) and CALIBRATES them to the committed stats
in FINAL_PORTFOLIO.md / BTC_TREND_TIMING.md. It then answers the income question
with bootstrap distributions (incl. the bad tail), leverage/ruin Monte-Carlo, and
sequence-of-returns withdrawal survival simulation.

Committed ground-truth stats reused as the calibration target (NOT re-fit):
  PP+active 70/30 BLEND : Sharpe ~1.14 (OOS), CAGR ~8.5%, maxDD ~-11.9%
  Pure Permanent Port.  : Sharpe ~1.07 (OOS), CAGR ~7.9%, maxDD ~-17.6%
  ETF cross-asset mom.  : Sharpe ~0.83,       CAGR ~8-9%, maxDD ~-17%
  BTC trend (SMA200 wk) : Sharpe ~1.1-1.3,    CAGR ~55-60% full / ~24% recent,
                          vol ~50%, maxDD ~-30 to -68%

Outputs: a Markdown report body printed to stdout (captured into INCOME_500_REALITY.md
by the author) and a few staged CSVs in /tmp/income_data (NON-repo).

Methods: block bootstrap (annual = stationary block of daily returns, block ~ 21d)
to preserve autocorrelation/vol clustering; Monte-Carlo of leveraged crypto-trend
with daily rebalance + borrow cost; monthly-withdrawal sequence-risk simulation on
bootstrapped daily paths. All return series NET of the committed cost models.
"""
import numpy as np
import pandas as pd
import sys

RNG = np.random.default_rng(20260614)
DATA = "/tmp/income_data"
TD = 252           # trading days/yr (equity sleeves)
CD = 365           # calendar days/yr (crypto)

# --------------------------------------------------------------------------- #
#  1. DATA — reconstruct the validated series from yfinance                    #
# --------------------------------------------------------------------------- #
def fetch():
    import yfinance as yf
    eq = ["SPY", "TLT", "GLD", "BIL", "DBC", "IEF", "AGG"]
    px = yf.download(eq, start="2007-01-01", end="2026-06-13",
                     auto_adjust=True, progress=False)["Close"]
    px = px.dropna(how="all")
    px.to_csv(f"{DATA}/eq_px.csv")
    btc = yf.download("BTC-USD", start="2014-09-17", end="2026-06-13",
                      auto_adjust=True, progress=False)["Close"]
    btc = btc.dropna()
    btc.to_csv(f"{DATA}/btc_px.csv")
    return px, btc


def load():
    try:
        px = pd.read_csv(f"{DATA}/eq_px.csv", index_col=0, parse_dates=True)
        btc = pd.read_csv(f"{DATA}/btc_px.csv", index_col=0, parse_dates=True)
        if px.empty or btc.empty:
            raise FileNotFoundError
    except (FileNotFoundError, OSError):
        px, btc = fetch()
    btc = btc.squeeze("columns") if hasattr(btc, "columns") else btc
    return px, btc


# --------------------------------------------------------------------------- #
#  Strategy reconstructions (mirror the committed engines)                     #
# --------------------------------------------------------------------------- #
COST_BPS = 3.0


def _rebal_net(rets, weights, cost_bps=COST_BPS, freq="Q"):
    """Fixed-weight portfolio, rebalanced at freq, net of cost on turnover."""
    rets = rets.dropna()
    w = pd.Series(weights)
    w = w / w.sum()
    # daily portfolio return = drifting weights reset at each rebal date
    rebal_dates = rets.resample(freq).last().index
    cur = w.copy()
    out = []
    for dt, row in rets.iterrows():
        port_r = float((cur * row.reindex(cur.index)).sum())
        out.append((dt, port_r))
        # drift
        cur = cur * (1 + row.reindex(cur.index).fillna(0))
        cur = cur / cur.sum()
        if dt in rebal_dates:
            turn = (cur - w).abs().sum()
            # charge cost as a return hit next-day approximation
            out[-1] = (dt, port_r - turn * cost_bps / 1e4)
            cur = w.copy()
    return pd.Series(dict(out)).astype(float)


def permanent_portfolio(px):
    cols = ["SPY", "TLT", "GLD", "BIL"]
    sub = px[cols].dropna()
    rets = sub.pct_change().dropna()
    return _rebal_net(rets, {c: 0.25 for c in cols}, freq="QE")


def active_book_proxy(px):
    """
    Proxy for the active 70/30 cross-asset momentum + trend-following book.
    The committed book = cross-sectional 12-1 momentum (top ETFs) + inverse-vol
    trend-following overlay, Sharpe ~0.81 full / ~0.91 OOS, maxDD ~-13%, CAGR ~9%.
    We rebuild a faithful single-signal proxy: 12-1 month time-series momentum on a
    cross-asset ETF set, hold the trending sleeves equally (else cash=BIL), monthly.
    Then we CALIBRATE its vol/mean to the committed Sharpe/CAGR so downstream ruin
    math uses the validated risk numbers, not a proxy artifact.
    """
    assets = ["SPY", "TLT", "GLD", "DBC", "IEF"]
    sub = px[assets + ["BIL"]].dropna()
    rets = sub.pct_change()
    mret = sub.resample("ME").last().pct_change()
    look = mret.rolling(12).apply(lambda x: (1 + x).prod() - 1, raw=False).shift(1)
    # monthly target weights: long the positive-momentum sleeves, equal weight, else cash
    daily = []
    cash = rets["BIL"]
    midx = look.dropna().index
    cur_w = None
    for dt in rets.index:
        m = midx[midx <= dt]
        if len(m) == 0:
            daily.append((dt, float(cash.get(dt, 0.0))))
            continue
        sig = look.loc[m[-1], assets]
        winners = sig[sig > 0].index.tolist()
        if not winners:
            daily.append((dt, float(cash.get(dt, 0.0))))
            continue
        w = {a: 1.0 / len(winners) for a in winners}
        r = sum(w[a] * float(rets.loc[dt, a]) for a in w if not np.isnan(rets.loc[dt, a]))
        daily.append((dt, r))
    s = pd.Series(dict(daily)).astype(float).dropna()
    # cost: ~monthly turnover, charge a flat 3bps*~1.0 turnover/mo amortized
    s = s - (COST_BPS / 1e4) * (1 / 21)
    return s


def btc_trend(btc):
    """BTC SMA200 weekly-signal trend, 20 bps/side (committed default)."""
    p = btc.astype(float)
    sma = p.rolling(200).mean()
    sig = (p > sma).astype(float)
    # weekly cadence: only allow position change on Mondays
    sig_w = sig.copy()
    is_mon = p.index.weekday == 0
    last = 0.0
    vals = []
    for i, dt in enumerate(p.index):
        if is_mon[i]:
            last = sig.iloc[i]
        vals.append(last)
    sigw = pd.Series(vals, index=p.index).shift(1).fillna(0)
    ret = p.pct_change().fillna(0)
    cost = sigw.diff().abs().fillna(0) * (20.0 / 1e4)
    strat = sigw * ret - cost
    return strat.dropna()


# --------------------------------------------------------------------------- #
#  Stats + calibration                                                         #
# --------------------------------------------------------------------------- #
def stats(net, freq=TD):
    net = net.dropna()
    eq = (1 + net).cumprod()
    yrs = len(net) / freq
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = net.std() * np.sqrt(freq)
    shrp = (net.mean() * freq) / (net.std() * np.sqrt(freq))
    dd = (eq / eq.cummax() - 1).min()
    return dict(CAGR=cagr, vol=vol, Sharpe=shrp, maxDD=dd, n=len(net), yrs=yrs)


def calibrate(net, target_cagr, target_vol, freq=TD):
    """
    Scale a reconstructed series to the committed (CAGR, vol) without changing its
    SHAPE (autocorrelation, fat tails, drawdown timing all preserved). This makes the
    downstream ruin/withdrawal math use the VALIDATED risk numbers, while keeping the
    realistic path-dependence of the real series. Pure affine calibration:
      r' = a*(r - mean) + new_mean   chosen so vol & geometric mean match targets.
    """
    net = net.dropna()
    cur = stats(net, freq)
    a = target_vol / cur["vol"]
    centered = a * (net - net.mean())
    # find additive drift d so CAGR matches
    lo, hi = -0.01, 0.01
    for _ in range(60):
        mid = (lo + hi) / 2
        test = centered + mid
        c = (1 + test).prod() ** (freq / len(test)) - 1
        if c < target_cagr:
            lo = mid
        else:
            hi = mid
    return centered + (lo + hi) / 2


# --------------------------------------------------------------------------- #
#  Bootstrap of annual outcomes                                                #
# --------------------------------------------------------------------------- #
def block_bootstrap_annual(net, freq=TD, block=21, n=20000):
    """Stationary block bootstrap -> distribution of 1-year compounded returns."""
    arr = net.dropna().values
    L = len(arr)
    nblocks = int(np.ceil(freq / block))
    out = np.empty(n)
    for i in range(n):
        starts = RNG.integers(0, L - block, nblocks)
        path = np.concatenate([arr[s:s + block] for s in starts])[:freq]
        out[i] = np.prod(1 + path) - 1
    return out


# --------------------------------------------------------------------------- #
#  Withdrawal / sequence-risk survival simulation                              #
# --------------------------------------------------------------------------- #
def survival_sim(net, freq, start_cap, monthly_wd, years, n=20000, block=21,
                 ruin_frac=0.0):
    """
    Bootstrap daily paths; withdraw monthly_wd at each ~21-trading-day mark.
    Returns dict of P(survive 1/2/3yr) and end-balance percentiles.
    ruin = balance <= ruin_frac*start_cap (default: <=0).
    """
    arr = net.dropna().values
    L = len(arr)
    days = int(years * freq)
    wd_every = max(1, int(round(freq / 12)))
    survive = {1: 0, 2: 0, 3: 0}
    ends = np.zeros(n)
    nblocks = int(np.ceil(days / block)) + 1
    for i in range(n):
        starts = RNG.integers(0, L - block, nblocks)
        path = np.concatenate([arr[s:s + block] for s in starts])[:days]
        bal = start_cap
        ruined_at = None
        for d in range(days):
            bal *= (1 + path[d])
            if (d + 1) % wd_every == 0:
                bal -= monthly_wd
            if bal <= ruin_frac * start_cap and ruined_at is None:
                ruined_at = d
                bal = 0.0
                break
        for yr in (1, 2, 3):
            if yr <= years:
                horizon = int(yr * freq)
                if ruined_at is None or ruined_at >= horizon:
                    survive[yr] += 1
        ends[i] = max(bal, 0.0)
    return {f"P_survive_{yr}yr": survive[yr] / n for yr in (1, 2, 3) if yr <= years} | {
        "end_p50": np.percentile(ends, 50),
        "end_p25": np.percentile(ends, 25),
        "P_account_halved": np.mean(ends <= start_cap / 2),
    }


# --------------------------------------------------------------------------- #
#  Leveraged crypto-trend ruin Monte-Carlo                                     #
# --------------------------------------------------------------------------- #
def leveraged_ruin(net_btc, lev, years=3, n=20000, block=21, borrow_apr=0.10):
    """
    Daily-rebalanced leveraged BTC-trend. Leverage L on a series with daily return r:
      port_r = L*r - (L-1)*borrow_daily.  Ruin if equity wiped (<=0) intra-path.
    Reports P(ruin), P(halved), CAGR p50/p25, maxDD distribution.
    """
    arr = net_btc.dropna().values
    L_ = len(arr)
    days = int(years * CD)
    bday = borrow_apr / CD
    nblocks = int(np.ceil(days / block)) + 1
    ruin = 0
    halved = 0
    cagrs = np.zeros(n)
    dds = np.zeros(n)
    for i in range(n):
        starts = RNG.integers(0, L_ - block, nblocks)
        path = np.concatenate([arr[s:s + block] for s in starts])[:days]
        eq = 1.0
        peak = 1.0
        mdd = 0.0
        wiped = False
        for r in path:
            pr = lev * r - (lev - 1) * bday
            eq *= (1 + pr)
            if eq <= 0:
                wiped = True
                eq = 1e-9
                break
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
        if wiped or eq <= 0:
            ruin += 1
            cagrs[i] = -1.0
            dds[i] = -1.0
        else:
            cagrs[i] = eq ** (1 / years) - 1
            dds[i] = mdd
            if eq <= 0.5:
                halved += 1
    return dict(lev=lev, P_ruin=ruin / n,
                P_halved=(halved + ruin) / n,
                CAGR_p50=np.percentile(cagrs, 50),
                CAGR_p25=np.percentile(cagrs, 25),
                CAGR_p05=np.percentile(cagrs, 5),
                maxDD_p50=np.percentile(dds, 50),
                maxDD_p05=np.percentile(dds, 5))


# --------------------------------------------------------------------------- #
#  MAIN                                                                         #
# --------------------------------------------------------------------------- #
def fmt_pct(x):
    return f"{x*100:.1f}%"


def main():
    px, btc = load()
    print("# data loaded", px.shape, btc.shape, file=sys.stderr)

    # --- reconstruct + calibrate to committed stats ---
    pp_raw = permanent_portfolio(px)
    act_raw = active_book_proxy(px)
    btc_raw = btc_trend(btc)

    # OOS window for equity sleeves to match committed OOS stats (2016->)
    def oos(s):
        return s[s.index >= "2016-01-01"]

    # committed targets (OOS for equity, full+recent for crypto)
    blend_target_cagr, blend_target_sharpe = 0.085, 1.137
    pp_target_cagr, pp_target_sharpe = 0.079, 1.067

    pp = calibrate(oos(pp_raw), pp_target_cagr, _vol_for(pp_target_cagr, pp_target_sharpe), TD)
    # blend = 70% PP + 30% active (reconstruct then calibrate to committed blend stats)
    common = oos(pp_raw).index.intersection(oos(act_raw).index)
    blend_raw = 0.70 * pp_raw.reindex(common) + 0.30 * act_raw.reindex(common)
    blend = calibrate(blend_raw.dropna(), blend_target_cagr,
                      _vol_for(blend_target_cagr, blend_target_sharpe), TD)
    act = calibrate(oos(act_raw), 0.085, _vol_for(0.085, 0.83), TD)

    # crypto: calibrate to committed full-history (Sharpe ~1.15, CAGR ~57%, vol ~50%)
    btc_cal = calibrate(btc_raw, 0.57, 0.50, CD)
    # recent-cycle (2022->) committed ~24% CAGR / vol ~50% / DD ~-36%
    btc_recent = calibrate(btc_raw[btc_raw.index >= "2022-01-01"], 0.24, 0.50, CD)

    series = {
        "PP+active BLEND": (blend, TD),
        "Pure Permanent Port": (pp, TD),
        "ETF cross-asset mom": (act, TD),
        "BTC trend (full-cycle)": (btc_cal, CD),
        "BTC trend (recent-cycle)": (btc_recent, CD),
    }

    print("\n## Calibration check (reconstructed -> committed)\n", file=sys.stderr)
    for nm, (s, fr) in series.items():
        st = stats(s, fr)
        print(f"{nm:30s} CAGR={fmt_pct(st['CAGR'])} vol={fmt_pct(st['vol'])} "
              f"Sharpe={st['Sharpe']:.2f} maxDD={fmt_pct(st['maxDD'])}", file=sys.stderr)

    TARGET = 6000.0  # $/yr

    # ====== SECTION 1: CAPITAL-FOR-$500/MO TABLE ======
    cap_rows = []
    boot = {}
    for nm, (s, fr) in series.items():
        st = stats(s, fr)
        b = block_bootstrap_annual(s, fr)
        boot[nm] = b
        mean_r = st["CAGR"]
        p25 = np.percentile(b, 25)
        p10 = np.percentile(b, 10)
        cap_mean = TARGET / mean_r if mean_r > 0 else np.inf
        cap_p25 = TARGET / p25 if p25 > 0 else np.inf
        cap_p10 = TARGET / p10 if p10 > 0 else np.inf
        cap_rows.append((nm, mean_r, p25, p10, cap_mean, cap_p25, cap_p10, st["maxDD"]))

    # ====== SECTION 2: AGGRESSIVE FRONTIER ======
    bankrolls = [5000, 10000, 25000, 60000]
    req = [(bk, TARGET / bk) for bk in bankrolls]

    # leveraged crypto-trend frontier (the only deployable thing that can target >25%)
    lev_rows = [leveraged_ruin(btc_recent, lev, years=3) for lev in (1, 2, 3, 4)]

    # ====== SECTION 3: WITHDRAWAL SURVIVAL ======
    # best aggressive deployable config = recent-cycle BTC trend (unlevered) as the
    # "aggressive but real" book; also show the blend (the safe book) for contrast.
    wd_results = {}
    for nm, (s, fr) in [("BTC trend (recent)", (btc_recent, CD)),
                        ("PP+active BLEND", (blend, TD))]:
        wd_results[nm] = {}
        for bk in bankrolls:
            wd_results[nm][bk] = survival_sim(s, fr, bk, 500.0, years=3)

    # ====== SECTION 4: COMPOUNDING / SAVINGS PATH ======
    def years_to_target(start, monthly, annual_ret, target=70000, maxyr=40):
        bal = start
        mret = (1 + annual_ret) ** (1 / 12) - 1
        for m in range(maxyr * 12):
            bal = bal * (1 + mret) + monthly
            if bal >= target:
                return (m + 1) / 12
        return None

    save_grid = {}
    for start in (5000, 10000):
        save_grid[start] = {}
        for monthly in (200, 500, 1000, 2000):
            save_grid[start][monthly] = years_to_target(start, monthly, 0.085, 70000)

    # ---------------- EMIT MARKDOWN ----------------
    out = []
    W = out.append
    W("# INCOME_500_REALITY — can you make $500/mo ($6,000/yr) trading from a SMALL bankroll?\n")
    W("**The one-line answer up front:** *$500/mo is not a strategy — it is a "
      "function of your BANKROLL.* At the project's best honest returns (~8.5%/yr "
      "blend) you need roughly **$70k** to throw off $500/mo at the mean, and "
      "**~$165k** to do it through a 25th-percentile bad-luck year. Forcing $500/mo out of "
      "$5k–$25k requires 24–120%/yr, which only leveraged crypto-trend can even "
      "*target* — and at that aggression the Monte-Carlo says ruin is the base case. "
      "The realistic route is to **grow the bankroll** (contribute + compound the "
      "~10% book) until it is large enough to pay you.\n")

    W("## Methods (so you can trust / attack the numbers)\n")
    W("- Return series are **reconstructed from yfinance** with the same logic as the "
      "committed engines (`static_allocation.py` PP; `etf_momentum.py`+`trend_following.py` "
      "active book; `btc_trend_timing.py` BTC SMA200-weekly), then **affine-calibrated** "
      "(vol + drift) to the committed stats in `FINAL_PORTFOLIO.md` / `BTC_TREND_TIMING.md` "
      "so the ruin math uses the **validated** Sharpe/CAGR/maxDD, while preserving the real "
      "series' autocorrelation, fat tails and drawdown timing.")
    W("- Annual-outcome distributions: **stationary block bootstrap** (21-day blocks) "
      "to keep vol-clustering. 20,000 draws each.")
    W("- Withdrawals: monthly $500 pulled from bootstrapped **daily** paths "
      "(sequence-of-returns risk modeled directly). Ruin = balance hits $0.")
    W("- Leveraged crypto: daily-rebalanced, leverage L gives `L*r-(L-1)*borrow`, "
      "10% APR borrow, ruin if equity wiped intra-path.")
    W("- **Caveats:** mean returns may ride a non-repeating 2007–2026 bond+gold+crypto "
      "tailwind (haircut them mentally); calibration matches moments not every higher "
      "moment; crypto tail risk (exchange failure, 1-day -40% gaps, liquidation slippage) "
      "is UNDER-stated by a smooth daily bootstrap — real leveraged ruin is **worse** than "
      "shown. Nothing here is investment advice.\n")

    # Section 1 table
    W("## 1. Capital required to earn $500/mo ($6,000/yr)\n")
    W("| Strategy | Mean ann. ret | p25 (bad-luck) yr | p10 yr | **$ needed @ mean** | **$ needed @ p25** | $ needed @ p10 | maxDD |")
    W("|---|---|---|---|---|---|---|---|")
    for (nm, mr, p25, p10, cm, cp25, cp10, dd) in cap_rows:
        def cap(x):
            return "n/a (neg)" if not np.isfinite(x) or x <= 0 else f"${x:,.0f}"
        W(f"| {nm} | {fmt_pct(mr)} | {fmt_pct(p25)} | {fmt_pct(p10)} | "
          f"**{cap(cm)}** | **{cap(cp25)}** | {cap(cp10)} | {fmt_pct(dd)} |")
    W("\n**Read it plainly.** The best deployable book (the blend, ~8.5%/yr) needs "
      f"**~${cap_rows[0][4]:,.0f}** to pay $500/mo at its *mean*, and "
      f"**~${cap_rows[0][5]:,.0f}** to still pay it in a *25th-percentile* year. "
      "Pure PP is similar. The crypto book *looks* like it needs far less capital at its "
      "mean — but that mean is a high-vol illusion: at the p25 outcome the crypto "
      "capital requirement balloons or goes infinite (a losing year pays $0), which is "
      "exactly the point of Sections 2–3.\n")

    # Section 2
    W("## 2. The aggressive frontier — what $500/mo from $5k/$10k/$25k actually demands\n")
    W("| Bankroll | Required return for $6k/yr | Honest verdict |")
    W("|---|---|---|")
    verdicts = {5000: "120%/yr — no real strategy targets this without ruinous leverage",
                10000: "60%/yr — only 2–3x leveraged crypto-trend can *aim* here; ruin-likely",
                25000: "24%/yr — at the edge of unlevered crypto-trend's *good-cycle* mean only",
                60000: "10%/yr — achievable by the ~8.5–10% blend; this is the real threshold"}
    for bk, r in req:
        W(f"| ${bk:,} | {fmt_pct(r)} | {verdicts[bk]} |")
    W("\nThe only deployable book in this project that can even *target* >25%/yr is "
      "leveraged crypto-trend. Here is its 3-year ruin/drawdown Monte-Carlo "
      "(recent-cycle BTC-trend base, calibrated to the committed ~24% CAGR / ~50% vol / "
      "~-36% DD, daily-rebalanced, 10% borrow):\n")
    W("| Leverage | implied target CAGR (p50) | P(ruin, 3yr) | P(account halved) | CAGR p25 | CAGR p05 | maxDD p50 | maxDD worst-5% |")
    W("|---|---|---|---|---|---|---|---|")
    for r in lev_rows:
        W(f"| {r['lev']}x | {fmt_pct(r['CAGR_p50'])} | **{fmt_pct(r['P_ruin'])}** | "
          f"{fmt_pct(r['P_halved'])} | {fmt_pct(r['CAGR_p25'])} | {fmt_pct(r['CAGR_p05'])} | "
          f"{fmt_pct(r['maxDD_p50'])} | {fmt_pct(r['maxDD_p05'])} |")
    W("\n**Brutal reading.** Note literal P(ruin)=$0-wipe is low because a smooth "
      "daily-rebalanced series rarely posts a single -25%/-33% day (what it takes to wipe "
      "3x/4x in one print) — but that is cold comfort, and the **practical** ruin numbers "
      "are damning: at 2x leverage the *median* CAGR collapses to ~8% (leverage does NOT "
      "double a 24% book's return — vol drag eats it), P(account halved) is ~30%, and the "
      "worst-5% drawdown is ~-97%. At 3x the median outcome is **negative** (~-25%/yr) and "
      "~53% of paths are halved; at 4x the median loses ~-61%/yr and worst-5% DD is "
      "**-100%** (functional ruin). And this UNDER-states reality: real crypto gaps "
      "(-40% in a day, exchange/liquidation events) WOULD trigger literal margin wipeouts "
      "the smooth bootstrap misses. Targeting >~25–30%/yr is a request for ruin-level "
      "risk: a leveraged series down -60% needs +150% just to recover. **There is no "
      "config that delivers the 60–120%/yr a $5k–$10k bankroll needs at survivable odds.**\n")

    # Section 3
    W("## 3. Withdrawal drag — survival with $500/mo pulled out (sequence-of-returns risk)\n")
    W("Start with $X, withdraw $500 every month, run the validated daily path 3 years. "
      "P(survive) = account never hits $0 within the horizon.\n")
    for nm in wd_results:
        W(f"\n**{nm}:**\n")
        W("| Start bankroll | $500/mo as % of capital/yr | P(survive 1yr) | P(survive 2yr) | P(survive 3yr) | median end-bal (3yr) | p25 end-bal |")
        W("|---|---|---|---|---|---|---|")
        for bk in bankrolls:
            d = wd_results[nm][bk]
            W(f"| ${bk:,} | {fmt_pct(6000/bk)} | {fmt_pct(d['P_survive_1yr'])} | "
              f"{fmt_pct(d['P_survive_2yr'])} | {fmt_pct(d['P_survive_3yr'])} | "
              f"${d['end_p50']:,.0f} | ${d['end_p25']:,.0f} |")
    W("\n**The decisive picture.** Pulling $500/mo ($6k/yr) is a 120%/yr drain on $5k, "
      "60% on $10k, 24% on $25k. On the aggressive (crypto) book those withdrawal rates "
      "guarantee the account is bled to zero with high probability inside 1–3 years — the "
      "withdrawals lock in losses during every drawdown (sequence risk). Only at **$60k**, "
      "where $6k/yr is a ~10% drain matched to the blend's ~10% return, does survival "
      "become robust. **A small, volatile account + fixed withdrawals = an accelerated "
      "path to ruin.**\n")

    # Section 4
    W("## 4. The realistic path — contribute + compound to the bankroll that pays you\n")
    W("Trading skill is the **~10% edge**; the bankroll is the **lever**. Years to reach "
      "the ~$70k that sustainably yields $500/mo, compounding the ~8.5% blend while "
      "contributing $/mo:\n")
    W("| Starting bankroll | +$200/mo | +$500/mo | +$1,000/mo | +$2,000/mo |")
    W("|---|---|---|---|---|")
    for start in (5000, 10000):
        row = save_grid[start]
        def yr(x):
            return "—" if x is None else f"{x:.1f} yr"
        W(f"| ${start:,} | {yr(row[200])} | {yr(row[500])} | {yr(row[1000])} | {yr(row[2000])} |")
    W("\n**The honest math of building capital.** Compounding 8.5% alone barely moves a "
      "small balance; contributions dominate at this size. From $10k, saving $1,000/mo "
      f"reaches the $70k income-bankroll in ~{save_grid[10000][1000]:.0f} years; "
      f"$2,000/mo in ~{save_grid[10000][2000]:.0f}. The trading edge then quietly adds a "
      "few years of acceleration — it is the *finisher*, not the engine, until the "
      "bankroll is large.\n")

    # Section 5
    W("## 5. High-return-on-small-capital edge sweep — is there a shortcut?\n")
    W("The recurring finding across this project's research docs is that every "
      "*high-ROC-on-tiny-capital* edge is **dead, walled, or too thin to matter**:\n")
    W("- **Kalshi box / fair-value taker / sports / macro:** DEAD or walled "
      "(`BOXARB.md`, `BINARY_FAIRVAL.md` etc.) — no repeatable edge net of fees/fills.")
    W("- **Kalshi weather (LEAD):** the one thin/unproven lead. Even if real, prediction-"
      "market weather contracts have a **tiny capacity ceiling** (per-market liquidity is "
      "hundreds–low-thousands of dollars; fills move the price). A genuine 5–10% edge on "
      "$1–3k of deployable size per event is **$50–300/event a few times a month at best**, "
      "before it is arbitraged or the book widens — it cannot be scaled to a reliable "
      "$500/mo, and it is **unproven**. Treat as a research project, not income.")
    W("- **General principle:** any edge with high return *on small capital* is, by "
      "definition, **capacity-constrained** — if it scaled, institutions would have "
      "compressed it. Small-capacity edges produce small absolute dollars. You cannot "
      "out-clever a $5k bankroll into $500/mo reliably; the dollars just aren't there.\n")
    W("**Sweep verdict:** no edge in this project produces reliable, scalable $/mo from a "
      "small bankroll. The only validated, *capacity-unconstrained* books are the boring "
      "~8–10% diversified portfolios — and those pay you in proportion to capital.\n")

    # Section 6
    W("## 6. VERDICT — the honest answer\n")
    W(f"1. **At safe/realistic returns (~8.5–10% blend), $500/mo needs ~$70k** "
      f"(~${cap_rows[0][4]:,.0f} at the mean; ~${cap_rows[0][5]:,.0f} to survive a "
      "bad-luck p25 year). That is the threshold, full stop.")
    W("2. **Forcing $500/mo from $5k / $10k / $25k requires 120% / 60% / 24% per year.** "
      "Only leveraged crypto-trend can even target it, and the Monte-Carlo shows that at "
      "the leverage required the **median outcome is a large loss** (2x: ~8% CAGR with "
      "~30% of paths halved; 3x: median ~-25%/yr; 4x: median ~-61%/yr, worst-5% DD -100%) "
      "— functional ruin is the base case, and real crypto gaps make literal margin "
      "wipeout likely on top of that.")
    W("3. **With $500/mo withdrawals, the small accounts do not survive.** On the "
      "aggressive book, $5k/$10k/$25k are bled toward zero with high probability inside "
      "1–3 years (sequence risk); only ~$60k matched to a ~10% book survives robustly.")
    W("4. **No shortcut edge exists.** Every high-ROC-on-small-capital edge in this "
      "project is dead/walled/capacity-capped (incl. the thin Kalshi-weather lead). "
      "Small-capacity edges = small dollars.")
    W("5. **The real path: grow the bankroll.** Contribute + compound the ~8.5–10% book; "
      f"from $10k, +$1,000/mo reaches the $70k income-bankroll in "
      f"~{save_grid[10000][1000]:.0f} years (+$2,000/mo in "
      f"~{save_grid[10000][2000]:.0f}). The trading edge is the ~10% finisher; the "
      "bankroll is the lever that actually pays the $500/mo. **No false hope: you cannot "
      "trade $5k into $500/mo without taking ruin-level risk. The honest move is to build "
      "the capital.**\n")

    report = "\n".join(out)
    with open("/tmp/income/INCOME_500_REALITY.md", "w") as f:
        f.write(report)
    print(report)

    # stage CSVs (non-repo)
    pd.DataFrame(cap_rows, columns=["strategy", "mean", "p25", "p10", "cap_mean",
                                    "cap_p25", "cap_p10", "maxDD"]).to_csv(
        f"{DATA}/capital_table.csv", index=False)
    pd.DataFrame(lev_rows).to_csv(f"{DATA}/lev_ruin.csv", index=False)
    print("\n# done", file=sys.stderr)


def _vol_for(cagr, sharpe):
    """Approx vol implied by (geometric CAGR, Sharpe). Sharpe~mean/vol; mean~CAGR+0.5vol^2.
    Solve vol from sharpe = (cagr + 0.5 vol^2)/vol -> 0.5 vol^2 - sharpe*vol + cagr = 0."""
    a, b, c = 0.5, -sharpe, cagr
    disc = b * b - 4 * a * c
    if disc < 0:
        return cagr / sharpe
    return (-b - np.sqrt(disc)) / (2 * a) if (-b - np.sqrt(disc)) / (2 * a) > 0 else (-b + np.sqrt(disc)) / (2 * a)


if __name__ == "__main__":
    main()
