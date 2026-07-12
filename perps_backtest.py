"""perps_backtest.py -- honest post-cost backtests of candidate perp strategies on REAL data.

Data source: Deribit public API (BTC-PERPETUAL, ETH-PERPETUAL). Chosen because it is the ONE
venue reachable from this sandbox that gives BOTH price candles AND funding-rate history from
the SAME instrument over a multi-year window:
  - Binance: HTTP 451 (geo-blocked) from this sandbox.
  - Bybit: CloudFront geo-block ("configured to block access from your country").
  - OKX: candles go back years (verified to 2020), but `funding-rate-history` hard-caps at
    ~90 days server-side (paging with `before=` past that point silently returns recent data
    instead of older data) -- confirmed both in this run and in this repo's prior work
    (CRYPTO_FUNDING.md). Not usable for a 1-3y funding backtest.
  - Coinbase Exchange: spot candles only, no perp/funding.
  - Deribit: `get_tradingview_chart_data` returns full multi-year daily history in ONE request
    (verified: 1,654 daily bars, 2021-12-31 -> 2026-07-11, for both BTC-PERPETUAL and
    ETH-PERPETUAL) and hourly candles in ~5,000-bar (~208-day) pages. `get_funding_rate_history`
    returns hourly `interest_1h` (the actually-charged rate for that hour) capped at 744 rows
    (~31 days) per call, paged by walking start/end forward.

LIMITATION flagged up front: this backtest uses Deribit's OWN perpetual (price + funding), a
single, real, live-traded instrument -- not a synthetic blend of one venue's price with another
venue's funding. That keeps price and funding internally consistent (no cross-venue basis
artifact), at the cost of being one venue's specific funding regime rather than a cross-exchange
average. Deribit is a real, liquid, institutional venue, but funding on Binance/OKX/Bybit can
differ from Deribit's in level (not generally in sign/regime). Documented in PERPS_BACKTEST.md.

No lookahead: every signal at bar t uses only data available at or before the close of bar t-1
(all signal series are explicitly `.shift(1)`-ed before use); every simulated fill happens at
bar t's close (i.e. one full bar of decision lag, close-to-close, no intrabar peeking).

    python perps_backtest.py                # fetch (or use cache), run everything, print tables
    python perps_backtest.py --refresh       # ignore cache, refetch
    python perps_backtest.py --years 3       # daily/funding history window (default 3)
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------
CACHE_DIR = os.environ.get("PERPS_CACHE_DIR", "/tmp/perps_backtest_cache")
BASE = "https://www.deribit.com/api/v2/public"
INSTRUMENTS = {"BTC": "BTC-PERPETUAL", "ETH": "ETH-PERPETUAL"}

# Cost assumptions (documented, not fitted). We use a conservative generic cross-venue retail
# taker/maker assumption (the task spec's 5-10bps taker / 1-2bps maker) rather than Deribit's
# own (often more favorable) fee schedule, since a strategy meant to generalize should clear
# realistic retail costs, not one venue's best-case tier.
TAKER_FEE = 0.0006     # 6 bps per fill (one side)
MAKER_FEE = 0.00015    # 1.5 bps per fill (one side)
CARRY_ROUNDTRIP_TAKER = 4 * TAKER_FEE   # 2-leg (spot+perp) open + close = 4 fills
CARRY_ROUNDTRIP_MAKER = 4 * MAKER_FEE

DAY_MS = 86_400_000


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------------------
# Data fetch (Deribit public REST, cached to parquet -- cache dir is NOT committed)
# --------------------------------------------------------------------------------------
def _get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "perps-backtest-research/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            time.sleep((2.0 if e.code in (403, 429, 502, 503) else 1.0) * (i + 1))
        except Exception:
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}")


def fetch_daily_candles(instrument, start_ms, end_ms):
    url = (f"{BASE}/get_tradingview_chart_data?instrument_name={instrument}"
           f"&start_timestamp={start_ms}&end_timestamp={end_ms}&resolution=1D")
    d = _get(url)["result"]
    if d.get("status") != "ok" or not d.get("ticks"):
        raise RuntimeError(f"bad daily candle response for {instrument}: {d.get('status')}")
    df = pd.DataFrame({"ts": d["ticks"], "open": d["open"], "high": d["high"],
                        "low": d["low"], "close": d["close"], "volume": d["volume"]})
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def fetch_hourly_candles(instrument, start_ms, end_ms, step_days=190):
    """Chunked: Deribit caps ~5000 rows/call (~208d hourly); walk forward in step_days windows."""
    frames = []
    cur = start_ms
    step_ms = step_days * DAY_MS
    while cur < end_ms:
        chunk_end = min(cur + step_ms, end_ms)
        url = (f"{BASE}/get_tradingview_chart_data?instrument_name={instrument}"
               f"&start_timestamp={cur}&end_timestamp={chunk_end}&resolution=60")
        d = _get(url)["result"]
        if d.get("status") == "ok" and d.get("ticks"):
            df = pd.DataFrame({"ts": d["ticks"], "open": d["open"], "high": d["high"],
                                "low": d["low"], "close": d["close"], "volume": d["volume"]})
            frames.append(df)
        cur = chunk_end
        time.sleep(0.15)
    if not frames:
        raise RuntimeError(f"no hourly candles for {instrument}")
    out = pd.concat(frames, ignore_index=True)
    out["ts"] = pd.to_datetime(out["ts"], unit="ms", utc=True)
    return out.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def fetch_funding(instrument, start_ms, end_ms, step_days=28):
    """Chunked: Deribit caps 744 rows/call (~31d hourly); walk forward. `interest_1h` is the
    rate actually accrued for that specific hour (the charged rate); `interest_8h` is a
    smoothed display value -- we use interest_1h so summed daily funding is the real total."""
    frames = []
    cur = start_ms
    step_ms = step_days * DAY_MS
    while cur < end_ms:
        chunk_end = min(cur + step_ms, end_ms)
        url = (f"{BASE}/get_funding_rate_history?instrument_name={instrument}"
               f"&start_timestamp={cur}&end_timestamp={chunk_end}")
        d = _get(url)["result"]
        if d:
            frames.append(pd.DataFrame(d))
        cur = chunk_end
        time.sleep(0.15)
    if not frames:
        raise RuntimeError(f"no funding history for {instrument}")
    out = pd.concat(frames, ignore_index=True)
    out["ts"] = pd.to_datetime(out["timestamp"], unit="ms", utc=True)
    out = out.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    return out[["ts", "interest_1h", "interest_8h", "index_price"]]


def load_or_fetch(name, fetch_fn, refresh=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{name}.parquet")
    if not refresh and os.path.exists(path):
        age_h = (time.time() - os.path.getmtime(path)) / 3600
        df = pd.read_parquet(path)
        log(f"  [cache] {name}: {len(df)} rows (age {age_h:.1f}h)")
        return df
    df = fetch_fn()
    df.to_parquet(path)
    log(f"  [fetch] {name}: {len(df)} rows -> {path}")
    return df


def get_all_data(years=3, refresh=False):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(years * 365.25))
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    data = {}
    for sym, inst in INSTRUMENTS.items():
        log(f"[data] {sym} ({inst}) daily candles ({years}y window)")
        data[f"{sym}_daily"] = load_or_fetch(f"{sym}_daily", lambda inst=inst: fetch_daily_candles(inst, start_ms, end_ms), refresh)
        log(f"[data] {sym} hourly candles")
        data[f"{sym}_hourly"] = load_or_fetch(f"{sym}_hourly", lambda inst=inst: fetch_hourly_candles(inst, start_ms, end_ms), refresh)
        log(f"[data] {sym} funding history")
        data[f"{sym}_funding"] = load_or_fetch(f"{sym}_funding", lambda inst=inst: fetch_funding(inst, start_ms, end_ms), refresh)
    data["_window"] = (start, end)
    return data


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------
def max_drawdown(equity):
    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    return dd.min()


def clustered_t(daily_pnl):
    """Day-clustered t-stat: daily_pnl must already be ONE observation per calendar day (sum
    intraday pnl into daily buckets first) so the t-stat isn't inflated by intraday
    autocorrelation. t = mean / (std/sqrt(n))."""
    x = daily_pnl.dropna()
    n = len(x)
    if n < 2 or x.std(ddof=1) == 0:
        return 0.0, n
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(n))), n


def perf_summary(pnl, periods_per_year, daily_pnl_for_t=None):
    """pnl: per-bar strategy return series (post-cost). Returns dict of Sharpe/Calmar/maxDD/etc."""
    pnl = pnl.dropna()
    if len(pnl) < 5:
        return dict(sharpe=np.nan, calmar=np.nan, max_dd=np.nan, ann_ret=np.nan,
                     pct_prof_months=np.nan, t_stat=np.nan, n_days=0, n_obs=len(pnl))
    equity = (1 + pnl).cumprod()
    n_years = len(pnl) / periods_per_year
    cagr = equity.iloc[-1] ** (1 / max(n_years, 1e-9)) - 1 if equity.iloc[-1] > 0 else -1.0
    mdd = max_drawdown(equity)
    sharpe = pnl.mean() / pnl.std(ddof=1) * np.sqrt(periods_per_year) if pnl.std(ddof=1) > 0 else np.nan
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    monthly = pnl.resample("ME").apply(lambda s: (1 + s).prod() - 1) if isinstance(pnl.index, pd.DatetimeIndex) else None
    pct_prof_months = float((monthly > 0).mean()) if monthly is not None and len(monthly) else np.nan
    if daily_pnl_for_t is None:
        daily_pnl_for_t = pnl if periods_per_year <= 366 else pnl.resample("D").sum()
    t_stat, n_days = clustered_t(daily_pnl_for_t)
    return dict(sharpe=sharpe, calmar=calmar, max_dd=mdd, ann_ret=cagr,
                pct_prof_months=pct_prof_months, t_stat=t_stat, n_days=n_days, n_obs=len(pnl))


def split_is_oos(df):
    n = len(df)
    return df.iloc[: n // 2], df.iloc[n // 2:]


def fmt_row(label, s):
    pm = s['pct_prof_months'] * 100 if not np.isnan(s['pct_prof_months']) else float('nan')
    return (f"{label:<32} sharpe={s['sharpe']:+6.2f}  calmar={s['calmar']:+6.2f}  "
            f"maxDD={s['max_dd']*100:+6.1f}%  annRet={s['ann_ret']*100:+7.1f}%  "
            f"%profMo={pm:5.1f}%  t(day-clu)={s['t_stat']:+5.2f}  n_days={s['n_days']}")


# --------------------------------------------------------------------------------------
# Strategy 1: Funding-rate carry (delta-neutral short-perp/long-spot when funding positive)
# --------------------------------------------------------------------------------------
def build_daily_funding(funding_df):
    f = funding_df.set_index("ts")["interest_1h"].resample("D").sum()
    return f


def funding_carry_backtest(sym, funding_daily, entry_thr_ann, exit_thr_ann, roundtrip_cost):
    """Delta-neutral carry: go short-perp/long-spot (collect funding) when the trailing 7d mean
    funding annualizes above +entry_thr; go long-perp/short-spot (collect negative funding) when
    it annualizes below -entry_thr; flat (hysteresis band) between -exit_thr and +exit_thr.
    Position decided on trailing (lagged) funding only -- no lookahead. P&L = position *
    (-funding_rate_that_day) - cost*|turnover|/2 (cost charged once per entry/exit leg change,
    not every day held)."""
    trail = funding_daily.rolling(7, min_periods=7).mean() * 365  # annualized trailing signal
    trail = trail.shift(1)  # lag 1 day: decide using info through yesterday
    pos = pd.Series(0.0, index=funding_daily.index)
    state = 0
    for i, val in enumerate(trail.values):
        if np.isnan(val):
            pos.iloc[i] = state
            continue
        if state == 0:
            if val > entry_thr_ann:
                state = -1   # short perp (collect funding: shorts receive when funding>0)
            elif val < -entry_thr_ann:
                state = 1    # long perp (collect funding: longs receive when funding<0)
        elif state == -1 and val < exit_thr_ann:
            state = 0
        elif state == 1 and val > -exit_thr_ann:
            state = 0
        pos.iloc[i] = state
    # holder of SHORT (pos=-1) receives +funding when funding>0: pnl = -pos*funding
    fund_pnl = -pos * funding_daily
    turns = pos.diff().abs().fillna(pos.abs())
    cost_pnl = -turns * roundtrip_cost / 2  # each unit of turnover = one entry OR exit (half roundtrip)
    pnl = fund_pnl + cost_pnl
    pnl.name = f"{sym}_carry"
    return pnl, pos


# --------------------------------------------------------------------------------------
# Strategy 2: Time-series momentum (daily / hourly), long AND short, with/without vol-scaling
# --------------------------------------------------------------------------------------
def ma_cross_signal(close, fast=20, slow=50):
    fast_ma = close.rolling(fast).mean()
    slow_ma = close.rolling(slow).mean()
    sig = np.sign(fast_ma - slow_ma)
    return sig.shift(1)  # lag 1 bar: trade on yesterday's cross


def donchian_signal(close, n=20):
    hi = close.rolling(n).max()
    lo = close.rolling(n).min()
    sig = pd.Series(np.nan, index=close.index)
    sig[close >= hi.shift(1)] = 1.0
    sig[close <= lo.shift(1)] = -1.0
    sig = sig.ffill().fillna(0.0)
    return sig.shift(1)


def momentum_signal(close, lookback):
    mom = close.pct_change(lookback)
    sig = np.sign(mom)
    return sig.shift(1)


def vol_scale(returns, target_ann_vol=0.5, periods_per_year=365, window=20, cap=2.0):
    rv = returns.rolling(window).std() * np.sqrt(periods_per_year)
    scale = (target_ann_vol / rv).clip(upper=cap)
    return scale.shift(1).fillna(1.0)


def run_ts_strategy(close, funding_per_bar, sig, periods_per_year, fee=TAKER_FEE, scale=None, sl=None, tp=None):
    """close: price series. funding_per_bar: series aligned to close.index (rate for holding
    through that bar; -pos*funding is the P&L sign convention -- cost to longs when funding>0).
    sig: -1/0/1 position ALREADY lagged (decided using info through the prior bar). scale:
    optional lagged position multiplier. sl/tp: fractional stop-loss / take-profit checked on
    close-to-close moves since entry (no intrabar high/low fill assumed -- conservative/approximate,
    documented limitation)."""
    ret = close.pct_change()
    pos = sig.fillna(0.0)
    if scale is not None:
        pos = pos * scale
    if sl is not None or tp is not None:
        entry_price = close.where(pos.diff().fillna(pos) != 0).ffill()
        adverse = np.where(pos > 0, close / entry_price - 1, np.where(pos < 0, entry_price / close - 1, 0.0))
        favorable = -adverse
        hit_sl = pd.Series(adverse, index=close.index) <= -(sl if sl is not None else 1e9)
        hit_tp = pd.Series(favorable, index=close.index) >= (tp if tp is not None else 1e9)
        force_flat = hit_sl | hit_tp
        pos = pos.where(~force_flat, 0.0)
    price_pnl = pos * ret
    fund_pnl = -pos * funding_per_bar.reindex(close.index).fillna(0.0)
    turns = pos.diff().abs().fillna(pos.abs())
    cost_pnl = -turns * fee
    pnl = price_pnl + fund_pnl + cost_pnl
    return pnl


# --------------------------------------------------------------------------------------
# Strategy 3: Mean reversion (hourly RSI / z-score fade)
# --------------------------------------------------------------------------------------
def rsi(close, n=14):
    delta = close.diff()
    up = delta.clip(lower=0).rolling(n).mean()
    down = (-delta.clip(upper=0)).rolling(n).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def zscore_signal(close, n=20, entry_z=1.0, exit_z=0.25):
    z = (close - close.rolling(n).mean()) / close.rolling(n).std()
    z = z.shift(1)
    pos = pd.Series(0.0, index=close.index)
    state = 0
    for i, val in enumerate(z.values):
        if np.isnan(val):
            pos.iloc[i] = state
            continue
        if state == 0:
            if val > entry_z:
                state = -1  # fade: price high vs mean -> short
            elif val < -entry_z:
                state = 1
        elif state == -1 and val < exit_z:
            state = 0
        elif state == 1 and val > -exit_z:
            state = 0
        pos.iloc[i] = state
    return pos


def rsi_signal(close, n=14, ob=70, os_=30, exit_mid=50):
    r = rsi(close, n).shift(1)
    pos = pd.Series(0.0, index=close.index)
    state = 0
    for i, val in enumerate(r.values):
        if np.isnan(val):
            pos.iloc[i] = state
            continue
        if state == 0:
            if val > ob:
                state = -1
            elif val < os_:
                state = 1
        elif state == -1 and val < exit_mid:
            state = 0
        elif state == 1 and val > exit_mid:
            state = 0
        pos.iloc[i] = state
    return pos


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--years", type=float, default=3.0)
    args = ap.parse_args()

    log("=" * 100)
    log("PERPS BACKTEST -- Deribit BTC-PERPETUAL / ETH-PERPETUAL, real price + real funding")
    log("Costs: taker=%.1fbps/fill  maker=%.2fbps/fill  carry roundtrip(taker)=%.1fbps" %
        (TAKER_FEE * 1e4, MAKER_FEE * 1e4, CARRY_ROUNDTRIP_TAKER * 1e4))
    log("=" * 100)

    data = get_all_data(years=args.years, refresh=args.refresh)
    start, end = data["_window"]
    log(f"\nWindow: {start.date()} -> {end.date()}  ({args.years}y requested)\n")

    results = {}

    # ============================= STRATEGY 1: FUNDING CARRY =============================
    log("\n" + "#" * 100)
    log("# STRATEGY 1 -- FUNDING CARRY (delta-neutral short-perp/long-spot when funding>0, reverse if <0)")
    log("#" * 100)
    for sym in ["BTC", "ETH"]:
        fdaily = build_daily_funding(data[f"{sym}_funding"])
        log(f"\n{sym}: funding daily series {fdaily.index.min().date()} -> {fdaily.index.max().date()} "
            f"({len(fdaily)} days), mean_ann={fdaily.mean()*365*100:.2f}%  %days_positive={float((fdaily>0).mean())*100:.1f}%")
        for entry_thr, exit_thr in [(0.02, 0.0), (0.05, 0.01), (0.10, 0.02), (0.20, 0.05)]:
            for cost_name, cost in [("taker(24bps rt)", CARRY_ROUNDTRIP_TAKER), ("maker(6bps rt)", CARRY_ROUNDTRIP_MAKER)]:
                pnl, pos = funding_carry_backtest(sym, fdaily, entry_thr, exit_thr, cost)
                s = perf_summary(pnl, 365)
                results[f"carry_{sym}_e{entry_thr}_x{exit_thr}_{cost_name}"] = s
                log(f"  entry={entry_thr*100:5.1f}% exit={exit_thr*100:5.1f}%  {cost_name:<16} " + fmt_row("", s))
        pnl, pos = funding_carry_backtest(sym, fdaily, 0.05, 0.01, CARRY_ROUNDTRIP_TAKER)
        is_pnl, oos_pnl = split_is_oos(pnl)
        log(f"  [{sym} carry entry=5%/exit=1%, taker] IS:  " + fmt_row("", perf_summary(is_pnl, 365)))
        log(f"  [{sym} carry entry=5%/exit=1%, taker] OOS: " + fmt_row("", perf_summary(oos_pnl, 365)))
        results[f"carry_{sym}_IS"] = perf_summary(is_pnl, 365)
        results[f"carry_{sym}_OOS"] = perf_summary(oos_pnl, 365)

    # ============================= STRATEGY 2: TS MOMENTUM (daily) =============================
    log("\n" + "#" * 100)
    log("# STRATEGY 2 -- TIME-SERIES MOMENTUM (daily bars), long+short, w/ and w/o vol-scaling")
    log("#" * 100)
    for sym in ["BTC", "ETH"]:
        d = data[f"{sym}_daily"].set_index("ts")["close"]
        fdaily = build_daily_funding(data[f"{sym}_funding"]).reindex(d.index).fillna(0.0)
        ret = d.pct_change()
        scale = vol_scale(ret, target_ann_vol=0.5, periods_per_year=365)
        configs = {
            "MA20/50 cross": ma_cross_signal(d, 20, 50),
            "Donchian-20 breakout": donchian_signal(d, 20),
            "24d momentum": momentum_signal(d, 24),
        }
        for name, sig in configs.items():
            for vs_name, sc in [("raw", None), ("vol-scaled", scale)]:
                pnl = run_ts_strategy(d, fdaily, sig, 365, fee=TAKER_FEE, scale=sc)
                s = perf_summary(pnl, 365)
                key = f"{sym} {name} [{vs_name}]"
                results[f"mom_{sym}_{name}_{vs_name}"] = s
                log(f"  {key:<48}" + fmt_row("", s))
                is_pnl, oos_pnl = split_is_oos(pnl)
                s_is, s_oos = perf_summary(is_pnl, 365), perf_summary(oos_pnl, 365)
                log(f"    IS : " + fmt_row("", s_is))
                log(f"    OOS: " + fmt_row("", s_oos))
                results[f"mom_{sym}_{name}_{vs_name}_IS"] = s_is
                results[f"mom_{sym}_{name}_{vs_name}_OOS"] = s_oos

    # ============================= STRATEGY 2b: 12h / 24h MOMENTUM (hourly bars) ===========
    log("\n" + "#" * 100)
    log("# STRATEGY 2b -- SHORT-HORIZON MOMENTUM (hourly bars, 12h/24h lookback), long+short")
    log("#" * 100)
    for sym in ["BTC", "ETH"]:
        h = data[f"{sym}_hourly"].set_index("ts")["close"]
        fh = data[f"{sym}_funding"].set_index("ts")["interest_1h"].reindex(h.index).fillna(0.0)
        ret = h.pct_change()
        scale = vol_scale(ret, target_ann_vol=0.5, periods_per_year=365 * 24, window=48)
        for lb, lb_name in [(12, "12h mom"), (24, "24h mom")]:
            sig = momentum_signal(h, lb)
            for vs_name, sc in [("raw", None), ("vol-scaled", scale)]:
                pnl = run_ts_strategy(h, fh, sig, 365 * 24, fee=TAKER_FEE, scale=sc)
                s = perf_summary(pnl, 365 * 24, daily_pnl_for_t=pnl.resample("D").sum())
                key = f"{sym} {lb_name} [{vs_name}]"
                results[f"hmom_{sym}_{lb_name}_{vs_name}"] = s
                log(f"  {key:<40}" + fmt_row("", s))
                is_pnl, oos_pnl = split_is_oos(pnl)
                s_is = perf_summary(is_pnl, 365 * 24, daily_pnl_for_t=is_pnl.resample("D").sum())
                s_oos = perf_summary(oos_pnl, 365 * 24, daily_pnl_for_t=oos_pnl.resample("D").sum())
                log(f"    IS : " + fmt_row("", s_is))
                log(f"    OOS: " + fmt_row("", s_oos))
                results[f"hmom_{sym}_{lb_name}_{vs_name}_IS"] = s_is
                results[f"hmom_{sym}_{lb_name}_{vs_name}_OOS"] = s_oos

    # ============================= STRATEGY 3: MEAN REVERSION (hourly) =====================
    log("\n" + "#" * 100)
    log("# STRATEGY 3 -- MEAN REVERSION (hourly RSI(14) fade / z-score(20h) fade), post-cost")
    log("#" * 100)
    for sym in ["BTC", "ETH"]:
        h = data[f"{sym}_hourly"].set_index("ts")["close"]
        fh = data[f"{sym}_funding"].set_index("ts")["interest_1h"].reindex(h.index).fillna(0.0)
        configs = {
            "RSI14 fade (70/30)": rsi_signal(h, 14, 70, 30),
            "zscore20h fade (1.0/0.25)": zscore_signal(h, 20, 1.0, 0.25),
        }
        for name, pos in configs.items():
            pnl = run_ts_strategy(h, fh, pos, 365 * 24, fee=TAKER_FEE, scale=None)
            s = perf_summary(pnl, 365 * 24, daily_pnl_for_t=pnl.resample("D").sum())
            key = f"{sym} {name}"
            results[f"mr_{sym}_{name}"] = s
            log(f"  {key:<40}" + fmt_row("", s))
            is_pnl, oos_pnl = split_is_oos(pnl)
            s_is = perf_summary(is_pnl, 365 * 24, daily_pnl_for_t=is_pnl.resample("D").sum())
            s_oos = perf_summary(oos_pnl, 365 * 24, daily_pnl_for_t=oos_pnl.resample("D").sum())
            log(f"    IS : " + fmt_row("", s_is))
            log(f"    OOS: " + fmt_row("", s_oos))
            results[f"mr_{sym}_{name}_IS"] = s_is
            results[f"mr_{sym}_{name}_OOS"] = s_oos

    # ============================= STRATEGY 4: SL/TP OVERLAY ================================
    log("\n" + "#" * 100)
    log("# STRATEGY 4 -- STOP-LOSS / TAKE-PROFIT OVERLAY on best OOS performer among #2/#2b/#3")
    log("#" * 100)
    candidates = []
    for k, s in results.items():
        if k.endswith("_OOS") and ("mom_" in k or "hmom_" in k or "mr_" in k):
            candidates.append((k, s["sharpe"] if not np.isnan(s["sharpe"]) else -999))
    candidates.sort(key=lambda x: -x[1])
    log("\nTop 5 by OOS Sharpe (post-cost, pre-SL/TP):")
    for k, sh in candidates[:5]:
        log(f"  {k:<55} OOS sharpe={sh:+.2f}")
    best_key = candidates[0][0][:-4] if candidates else None
    log(f"\nBest OOS performer selected for SL/TP overlay test: {best_key}")

    if best_key and best_key.startswith("mom_"):
        _, sym, name, vs_name = best_key.split("_", 3)
        d = data[f"{sym}_daily"].set_index("ts")["close"]
        fdaily = build_daily_funding(data[f"{sym}_funding"]).reindex(d.index).fillna(0.0)
        sig_map = {"MA20/50 cross": ma_cross_signal(d, 20, 50),
                   "Donchian-20 breakout": donchian_signal(d, 20),
                   "24d momentum": momentum_signal(d, 24)}
        sig = sig_map[name]
        ret = d.pct_change()
        sc = vol_scale(ret, 0.5, 365) if "vol-scaled" in vs_name else None
        base_pnl = run_ts_strategy(d, fdaily, sig, 365, fee=TAKER_FEE, scale=sc)
        base_s = perf_summary(base_pnl, 365)
        log(f"\n  BASE ({best_key}), full sample: " + fmt_row("", base_s))
        for sl, tp in [(None, None), (0.03, None), (0.05, None), (0.08, None),
                       (None, 0.05), (None, 0.10), (0.03, 0.06), (0.05, 0.10)]:
            pnl = run_ts_strategy(d, fdaily, sig, 365, fee=TAKER_FEE, scale=sc, sl=sl, tp=tp)
            s = perf_summary(pnl, 365)
            tag = f"sl={sl if sl else '-'} tp={tp if tp else '-'}"
            results[f"sltp_{best_key}_{tag}"] = s
            log(f"  {tag:<20}" + fmt_row("", s))
    elif best_key and best_key.startswith("hmom_"):
        _, sym, lb_name, vs_name = best_key.split("_", 3)
        h = data[f"{sym}_hourly"].set_index("ts")["close"]
        fh = data[f"{sym}_funding"].set_index("ts")["interest_1h"].reindex(h.index).fillna(0.0)
        lb = 12 if "12h" in lb_name else 24
        sig = momentum_signal(h, lb)
        ret = h.pct_change()
        sc = vol_scale(ret, 0.5, 365 * 24, window=48) if "vol-scaled" in vs_name else None
        base_pnl = run_ts_strategy(h, fh, sig, 365 * 24, fee=TAKER_FEE, scale=sc)
        base_s = perf_summary(base_pnl, 365 * 24, daily_pnl_for_t=base_pnl.resample("D").sum())
        log(f"\n  BASE ({best_key}), full sample: " + fmt_row("", base_s))
        for sl, tp in [(None, None), (0.01, None), (0.02, None), (0.03, None),
                       (None, 0.02), (None, 0.04), (0.01, 0.02), (0.02, 0.04)]:
            pnl = run_ts_strategy(h, fh, sig, 365 * 24, fee=TAKER_FEE, scale=sc, sl=sl, tp=tp)
            s = perf_summary(pnl, 365 * 24, daily_pnl_for_t=pnl.resample("D").sum())
            tag = f"sl={sl if sl else '-'} tp={tp if tp else '-'}"
            results[f"sltp_{best_key}_{tag}"] = s
            log(f"  {tag:<20}" + fmt_row("", s))
    elif best_key and best_key.startswith("mr_"):
        parts = best_key.split("_", 2)
        sym, name = parts[1], parts[2]
        h = data[f"{sym}_hourly"].set_index("ts")["close"]
        fh = data[f"{sym}_funding"].set_index("ts")["interest_1h"].reindex(h.index).fillna(0.0)
        pos = rsi_signal(h, 14, 70, 30) if "RSI" in name else zscore_signal(h, 20, 1.0, 0.25)
        base_pnl = run_ts_strategy(h, fh, pos, 365 * 24, fee=TAKER_FEE)
        base_s = perf_summary(base_pnl, 365 * 24, daily_pnl_for_t=base_pnl.resample("D").sum())
        log(f"\n  BASE ({best_key}), full sample: " + fmt_row("", base_s))
        for sl, tp in [(None, None), (0.01, None), (0.02, None), (0.03, None),
                       (None, 0.01), (None, 0.02), (0.01, 0.02), (0.02, 0.03)]:
            pnl = run_ts_strategy(h, fh, pos, 365 * 24, fee=TAKER_FEE, sl=sl, tp=tp)
            s = perf_summary(pnl, 365 * 24, daily_pnl_for_t=pnl.resample("D").sum())
            tag = f"sl={sl if sl else '-'} tp={tp if tp else '-'}"
            results[f"sltp_{best_key}_{tag}"] = s
            log(f"  {tag:<20}" + fmt_row("", s))

    log("\n" + "=" * 100)
    log("DONE. %d result rows computed. See PERPS_BACKTEST.md for the curated tables + verdicts." % len(results))
    log("=" * 100)
    return results


if __name__ == "__main__":
    main()
