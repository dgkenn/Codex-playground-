#!/usr/bin/env python3
"""
BTC derivatives-positioning short-horizon predictability backtest.

Question
--------
Do BTC futures derivatives-positioning signals (open interest change, top-trader &
global long/short ratios, taker buy/sell volume imbalance, funding) predict short-
horizon (5/15/30 min) forward BTC-perp returns, OUT-OF-SAMPLE across years, NET of cost?

Data (Binance Vision, USD-M futures)
------------------------------------
  metrics 5-min : futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-YYYY-MM-DD.zip
      cols: create_time, symbol, sum_open_interest, sum_open_interest_value,
            count_toptrader_long_short_ratio, sum_toptrader_long_short_ratio,
            count_long_short_ratio, sum_taker_long_short_vol_ratio
  klines 5m     : futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-YYYY-MM-DD.zip
  funding month : futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-YYYY-MM.zip

Disk discipline: download one day, parse to the 288 5-min feature rows IN MEMORY,
keep only the tiny parsed rows, DELETE raw immediately. Never accumulate raw.

Causality / anti-artifact
-------------------------
  * Every feature uses ONLY data up to timestamp t (levels + causal trailing z).
  * Normalisation windows are TRAILING and computed WITHIN each sampled day
    (sampled days are non-contiguous, so gluing them for a rolling window would be
    a leak / mixing across regimes; within-day expanding-trailing z, min_periods,
    is the causal best available). Funding z is trailing within its month.
  * Forward targets are strictly FUTURE close-to-close returns, computed WITHIN day
    (targets that would cross the day boundary are NaN and dropped) -> no cross-day
    look-ahead, no gluing leak.
  * Mandatory round-trip costs {1bp, 5bp}.
  * TRAIN = earliest 70% of sampled days, TEST = most recent 30%. Reported BOTH.
  * Day-clustered t-stat (cluster by calendar day) for every trade rule.
  * FULL grid reported (every signal x horizon x cost, momentum AND reversion, plus
    the 4 named classic setups) so multiple-testing is visible. No per-day cherry pick.

Verdict rule: a rule "survives" only if, for some (horizon,cost), its mean bps/trade
has the SAME SIGN in TRAIN and TEST AND |day-clustered t| >= 2.0 in BOTH.
"""
import os, io, sys, time, zipfile, warnings, math
import numpy as np
import pandas as pd
import requests

warnings.simplefilter("ignore")
pd.options.mode.chained_assignment = None

SCRATCH = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad"
RAW = os.path.join(SCRATCH, "raw_deriv")
os.makedirs(RAW, exist_ok=True)
REPORT = "/home/user/Codex-playground-/btc_derivatives_report.md"

M_URL = "https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-{d}.zip"
K_URL = "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-{d}.zip"
F_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-{m}.zip"

TODAY = pd.Timestamp("2026-07-15")
HORIZONS = [1, 3, 6]          # bars -> 5, 15, 30 min
COSTS = [1.0, 5.0]            # bps round trip
ZTHR = 1.0
ZWIN = 288                    # trailing window (=1 day of 5-min bars); within-day expanding
ZMINP = 24                    # min periods for a trailing z (2h)

# ---------------------------------------------------------------- sampling
def sample_dates():
    ds = []
    for year in range(2022, 2027):
        for month in range(1, 13):
            for day in (6, 16, 26):        # ~3 days / month across regimes
                try:
                    ts = pd.Timestamp(year=year, month=month, day=day)
                except ValueError:
                    continue
                if ts <= TODAY:
                    ds.append(ts.strftime("%Y-%m-%d"))
    return ds

# ---------------------------------------------------------------- download helpers
def fetch(url, session, tries=3):
    for i in range(tries):
        try:
            r = session.get(url, timeout=120)
        except Exception as e:
            time.sleep(1.5 * (i + 1)); last = f"err:{e}"; continue
        if r.status_code == 200:
            return ("ok", r.content)
        if r.status_code == 404:
            return ("404", None)
        last = f"http_{r.status_code}"; time.sleep(1.0 * (i + 1))
    return (last, None)

def read_zip_csv(content):
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = z.namelist()[0]
        return z.read(name)

def read_csv_robust(raw, names):
    """Binance Vision files sometimes have a header row, sometimes not (older files).
    Detect by testing whether the first field of the first line is numeric; assign
    canonical column names either way."""
    first = raw.split(b"\n", 1)[0].split(b",")[0].strip()
    try:
        float(first)
        has_header = False
    except ValueError:
        has_header = True
    if has_header:
        df = pd.read_csv(io.BytesIO(raw))
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.read_csv(io.BytesIO(raw), header=None, names=names)

_funding_cache = {}
def get_funding_month(mstr, session):
    """Return DataFrame(calc_time[ns], rate, rate_z) for month, trailing z within month."""
    if mstr in _funding_cache:
        return _funding_cache[mstr]
    status, content = fetch(F_URL.format(m=mstr), session)
    if status != "ok":
        _funding_cache[mstr] = None
        return None
    raw = read_zip_csv(content)
    df = read_csv_robust(raw, ["calc_time", "funding_interval_hours", "last_funding_rate"])
    df = df.rename(columns={"last_funding_rate": "rate"})
    df["calc_time"] = pd.to_datetime(df["calc_time"], unit="ms")
    df = df.sort_values("calc_time").reset_index(drop=True)
    # causal trailing z within month (expanding, min 6 obs = 2 days)
    m = df["rate"].expanding(min_periods=6).mean()
    s = df["rate"].expanding(min_periods=6).std(ddof=1)
    df["rate_z"] = (df["rate"] - m) / s.replace(0, np.nan)
    out = df[["calc_time", "rate", "rate_z"]]
    _funding_cache[mstr] = out
    return out

# ---------------------------------------------------------------- process one day
def process_day(dstr, session):
    sm, mc = fetch(M_URL.format(d=dstr), session)
    if sm != "ok":
        return sm, None
    sk, kc = fetch(K_URL.format(d=dstr), session)
    if sk != "ok":
        return f"klines_{sk}", None
    # metrics
    dm = read_csv_robust(read_zip_csv(mc), [
        "create_time", "symbol", "sum_open_interest", "sum_open_interest_value",
        "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
        "count_long_short_ratio", "sum_taker_long_short_vol_ratio"])
    ct = dm["create_time"]
    if np.issubdtype(pd.Series(ct).dtype, np.number):
        dm["ts"] = pd.to_datetime(ct.astype("int64"), unit="ms")
    else:
        dm["ts"] = pd.to_datetime(ct)
    dm = dm.rename(columns={
        "sum_open_interest": "oi",
        "sum_toptrader_long_short_ratio": "ls_top",
        "count_long_short_ratio": "ls_glob",
        "sum_taker_long_short_vol_ratio": "taker",
    })[["ts", "oi", "ls_top", "ls_glob", "taker"]]
    # klines
    dk = read_csv_robust(read_zip_csv(kc), [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"])
    dk["ts"] = pd.to_datetime(dk["open_time"].astype("int64"), unit="ms")
    dk = dk.rename(columns={"close": "close"})[["ts", "close"]]
    df = dm.merge(dk, on="ts", how="inner").sort_values("ts").reset_index(drop=True)
    if len(df) < 60:
        return "too_few_rows", None
    for c in ["oi", "ls_top", "ls_glob", "taker", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # funding asof
    mstr = dstr[:7]
    fu = get_funding_month(mstr, session)
    if fu is not None:
        df = pd.merge_asof(df, fu, left_on="ts", right_on="calc_time", direction="backward")
        df = df.drop(columns=["calc_time"])
        df = df.rename(columns={"rate": "funding", "rate_z": "funding_z"})
    else:
        df["funding"] = np.nan; df["funding_z"] = np.nan
    df["date"] = df["ts"].dt.strftime("%Y-%m-%d")
    return "ok", df

# ---------------------------------------------------------------- feature engineering
def zcausal(s):
    m = s.rolling(ZWIN, min_periods=ZMINP).mean()
    sd = s.rolling(ZWIN, min_periods=ZMINP).std(ddof=1)
    return (s - m) / sd.replace(0, np.nan)

def build_features(df):
    g = df.groupby("date", group_keys=False)
    # causal price return (past)
    df["ret_1"] = g["close"].transform(lambda s: np.log(s / s.shift(1)))
    df["ret_3"] = g["close"].transform(lambda s: np.log(s / s.shift(3)))
    # d_OI pct change
    df["dOI_1"] = g["oi"].transform(lambda s: s.pct_change(1))
    df["dOI_3"] = g["oi"].transform(lambda s: s.pct_change(3))
    # trailing causal z of levels/changes (within day)
    for col in ["ls_top", "ls_glob", "taker", "dOI_1", "dOI_3", "ret_1", "ret_3"]:
        df[col + "_z"] = g[col].transform(zcausal)
    # funding_z already trailing within month; also provide level
    # forward targets (future only, within day)
    for h in HORIZONS:
        df[f"fwd_{h}"] = g["close"].transform(lambda s: np.log(s.shift(-h) / s))
    return df

# ---------------------------------------------------------------- evaluation
def day_clustered_t(sub):
    """sub has columns date,pnl. Returns (mean_bps_per_trade, n_trades, n_days, t)."""
    if len(sub) == 0:
        return (np.nan, 0, 0, np.nan)
    per_day = sub.groupby("date")["pnl"].mean()
    n_days = len(per_day)
    mean_bps = sub["pnl"].mean()
    if n_days < 2:
        return (mean_bps, len(sub), n_days, np.nan)
    m = per_day.mean(); sd = per_day.std(ddof=1)
    t = m / (sd / math.sqrt(n_days)) if sd > 0 else np.nan
    return (mean_bps, len(sub), n_days, t)

def eval_rule(df, dir_series, h, cost):
    """dir_series: -1/0/+1 per bar. Returns dict of train/test stats."""
    fwd = df[f"fwd_{h}"]
    mask = (dir_series != 0) & fwd.notna()
    d = pd.DataFrame({
        "date": df["date"][mask],
        "is_train": df["is_train"][mask],
        "pnl": dir_series[mask] * fwd[mask] * 1e4 - cost,
    })
    tr = d[d["is_train"]]
    te = d[~d["is_train"]]
    return {"train": day_clustered_t(tr[["date", "pnl"]]),
            "test":  day_clustered_t(te[["date", "pnl"]])}

def corr_hit(df, sig, h, train):
    sub = df[df["is_train"] == train]
    x = sub[sig]; y = sub[f"fwd_{h}"]
    m = x.notna() & y.notna()
    x = x[m]; y = y[m]
    if len(x) < 30 or x.std() == 0 or y.std() == 0:
        return (np.nan, np.nan, len(x))
    r = np.corrcoef(x, y)[0, 1]
    hit = float((np.sign(x) == np.sign(y)).mean())
    return (r, hit, len(x))

# ---------------------------------------------------------------- main
def main():
    sess = requests.Session()
    sess.headers.update({"User-Agent": "research/1.0"})
    dates = sample_dates()
    print(f"Attempting {len(dates)} sampled dates {dates[0]}..{dates[-1]}", flush=True)

    frames = []
    status_counts = {}
    for i, d in enumerate(dates):
        st, df = process_day(d, sess)
        status_counts[st if st in ("ok",) else st.split("_")[0]] = \
            status_counts.get(st if st in ("ok",) else st.split("_")[0], 0) + 1
        if st == "ok":
            frames.append(df)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(dates)} done, kept {len(frames)} days", flush=True)
    print("status:", status_counts, flush=True)

    if len(frames) < 30:
        print("FATAL: too few days", file=sys.stderr); sys.exit(1)

    alld = pd.concat(frames, ignore_index=True)
    alld = build_features(alld)

    # train/test split by unique day (earliest 70% train)
    udays = sorted(alld["date"].unique())
    n_tr = int(round(len(udays) * 0.70))
    train_days = set(udays[:n_tr])
    alld["is_train"] = alld["date"].isin(train_days)
    span = f"{udays[0]}..{udays[-1]}"
    print(f"Kept {len(udays)} days, span {span}; train {n_tr} days, test {len(udays)-n_tr} days", flush=True)

    # ---- signal grid for corr + z-momentum/reversion ----
    # (signal_z used for both corr and dir=sign(z))
    signals = {
        "dOI_1":   "dOI_1_z",
        "dOI_3":   "dOI_3_z",
        "ls_top":  "ls_top_z",
        "ls_glob": "ls_glob_z",
        "taker":   "taker_z",
        "funding": "funding_z",
        "ret_1":   "ret_1_z",
        "ret_3":   "ret_3_z",
    }

    lines = []
    def P(s=""):
        lines.append(s)

    P("# BTC Derivatives-Positioning Short-Horizon Predictability - Backtest Report")
    P("")
    P(f"Generated {pd.Timestamp.utcnow():%Y-%m-%d %H:%M} UTC. Model produced numbers, verbatim below.")
    P("")
    P("## Sample achieved")
    P("")
    P(f"- Days kept: **{len(udays)}**  span **{span}**")
    P(f"- Dates attempted: {len(dates)} (3/month, 2022-01..today). Status: `{status_counts}`")
    P(f"- Rows (5-min bars): {len(alld):,}")
    P(f"- Split: TRAIN earliest **{n_tr}** days, TEST recent **{len(udays)-n_tr}** days (by calendar day).")
    P(f"- Horizons: +1/+3/+6 bars = 5/15/30 min. Costs: {COSTS} bps round-trip. z-threshold |z|>={ZTHR}.")
    P("- Features strictly causal (trailing within-day z; funding z trailing within month). "
      "Targets strictly future within-day close-to-close log returns.")
    P("")

    # ---------------- Test 1: corr + sign-hit (train & test) ----------------
    P("## Test 1 - Correlation & sign-hit of signal z vs forward return")
    P("")
    P("`r` = Pearson corr(signal_z, fwd_ret); `hit` = P(sign(z)=sign(fwd)). "
      "Overlapping targets inflate corr significance, so these are DESCRIPTIVE; "
      "the day-clustered trade t-stats in Test 2 are the robust arbiter.")
    P("")
    P("| signal | horizon | r_train | hit_train | r_test | hit_test | n_test |")
    P("|---|---|---|---|---|---|---|")
    corr_rows = []
    for name, sig in signals.items():
        for h in HORIZONS:
            rtr, htr, ntr = corr_hit(alld, sig, h, True)
            rte, hte, nte = corr_hit(alld, sig, h, False)
            P(f"| {name} | {h*5}m | {rtr:+.4f} | {htr:.3f} | {rte:+.4f} | {hte:.3f} | {nte:,} |")
            corr_rows.append((name, h, rtr, rte))
    P("")

    # ---------------- Test 2: tradeable z rules (momentum & reversion) ----------------
    survivors = []
    P("## Test 2 - Tradeable rule: dir = sign(signal z), |z| >= 1, hold horizon, net cost")
    P("")
    P("Reported for BOTH directions of the bet: **MOM** = trade with sign(z) "
      "(dir=+sign z), **REV** = trade against sign(z) (dir=-sign z). "
      "`t` is DAY-CLUSTERED. bps = mean net bps/trade. A cell SURVIVES only if same-sign "
      "mean bps in train & test AND |t|>=2 in both.")
    P("")
    for mode, mult in [("MOM", 1.0), ("REV", -1.0)]:
        P(f"### Mode {mode} (dir = {'+' if mult>0 else '-'}sign z)")
        P("")
        P("| signal | horizon | cost | train_bps | train_t | train_n | test_bps | test_t | test_n | survive |")
        P("|---|---|---|---|---|---|---|---|---|---|")
        for name, sig in signals.items():
            z = alld[sig]
            dir_s = pd.Series(np.where(z >= ZTHR, mult, np.where(z <= -ZTHR, -mult, 0.0)),
                              index=alld.index)
            for h in HORIZONS:
                for cost in COSTS:
                    res = eval_rule(alld, dir_s, h, cost)
                    (mb_tr, n_tr2, nd_tr, t_tr) = res["train"]
                    (mb_te, n_te2, nd_te, t_te) = res["test"]
                    surv = (np.isfinite(t_tr) and np.isfinite(t_te)
                            and abs(t_tr) >= 2 and abs(t_te) >= 2
                            and np.sign(mb_tr) == np.sign(mb_te))
                    tag = "**YES**" if surv else ""
                    if surv:
                        survivors.append((f"{mode} {name}", f"{h*5}m", cost, mb_tr, t_tr, mb_te, t_te))
                    P(f"| {name} | {h*5}m | {cost:.0f}bp | {mb_tr:+.2f} | {t_tr:+.2f} | {n_tr2} "
                      f"| {mb_te:+.2f} | {t_te:+.2f} | {n_te2} | {tag} |")
        P("")

    # ---------------- Named classic setups ----------------
    P("## Test 3 - Classic named setups (directional filters)")
    P("")
    P("(a) OI-up & price-up => continuation long; (b) OI-down & price-up => fade (short); "
      "(c) extreme crowded L/S ratio => contrarian; (d) extreme funding => fade funded side. "
      "Two-sided completions included where natural. Day-clustered t, both costs.")
    P("")

    # dir builders
    dOI1 = alld["dOI_1"]; r1 = alld["ret_1"]
    ls_top_z = alld["ls_top_z"]; ls_glob_z = alld["ls_glob_z"]; fund_z = alld["funding_z"]
    setups = {}
    # (a) continuation: OI up & price up -> long ; symmetric: OI up & price down -> short
    setups["(a) OI-up cont (long only)"] = pd.Series(np.where((dOI1 > 0) & (r1 > 0), 1.0, 0.0), index=alld.index)
    setups["(a') OI-up cont (2-sided)"] = pd.Series(
        np.where((dOI1 > 0) & (r1 > 0), 1.0, np.where((dOI1 > 0) & (r1 < 0), -1.0, 0.0)), index=alld.index)
    # (b) OI-down & price-up -> fade short ; symmetric OI-down & price-down -> fade long
    setups["(b) OI-dn fade (short only)"] = pd.Series(np.where((dOI1 < 0) & (r1 > 0), -1.0, 0.0), index=alld.index)
    setups["(b') OI-dn fade (2-sided)"] = pd.Series(
        np.where((dOI1 < 0) & (r1 > 0), -1.0, np.where((dOI1 < 0) & (r1 < 0), 1.0, 0.0)), index=alld.index)
    # (c) crowded top-trader ratio contrarian: z>=1 crowded long -> short
    setups["(c) crowd ls_top contrarian"] = pd.Series(
        np.where(ls_top_z >= ZTHR, -1.0, np.where(ls_top_z <= -ZTHR, 1.0, 0.0)), index=alld.index)
    setups["(c) crowd ls_glob contrarian"] = pd.Series(
        np.where(ls_glob_z >= ZTHR, -1.0, np.where(ls_glob_z <= -ZTHR, 1.0, 0.0)), index=alld.index)
    # (d) extreme funding fade: fund_z>=1 (longs pay) -> short
    setups["(d) funding fade"] = pd.Series(
        np.where(fund_z >= ZTHR, -1.0, np.where(fund_z <= -ZTHR, 1.0, 0.0)), index=alld.index)

    P("| setup | horizon | cost | train_bps | train_t | train_n | test_bps | test_t | test_n | survive |")
    P("|---|---|---|---|---|---|---|---|---|---|")
    for sname, dir_s in setups.items():
        for h in HORIZONS:
            for cost in COSTS:
                res = eval_rule(alld, dir_s, h, cost)
                (mb_tr, n_tr2, nd_tr, t_tr) = res["train"]
                (mb_te, n_te2, nd_te, t_te) = res["test"]
                surv = (np.isfinite(t_tr) and np.isfinite(t_te)
                        and abs(t_tr) >= 2 and abs(t_te) >= 2
                        and np.sign(mb_tr) == np.sign(mb_te))
                tag = "**YES**" if surv else ""
                if surv:
                    survivors.append((sname, f"{h*5}m", cost, mb_tr, t_tr, mb_te, t_te))
                P(f"| {sname} | {h*5}m | {cost:.0f}bp | {mb_tr:+.2f} | {t_tr:+.2f} | {n_tr2} "
                  f"| {mb_te:+.2f} | {t_te:+.2f} | {n_te2} | {tag} |")
    P("")

    # ---------------- Verdict ----------------
    P("## VERDICT")
    P("")
    if survivors:
        P(f"**{len(survivors)} rule(s) SURVIVED** (same-sign mean bps in train & test, "
          f"|day-clustered t|>=2 in BOTH):")
        P("")
        P("| rule | horizon | cost | train_bps | train_t | test_bps | test_t |")
        P("|---|---|---|---|---|---|---|")
        for s in survivors:
            P(f"| {s[0]} | {s[1]} | {s[2]:.0f}bp | {s[3]:+.2f} | {s[4]:+.2f} | {s[5]:+.2f} | {s[6]:+.2f} |")
        P("")
        P("Interpretation: these passed a strict OOS + cost + day-clustered bar. "
          "Given the size of the grid, weigh against multiple testing before deployment.")
    else:
        P("**NO rule survived.** Across the full grid (8 signals x 3 horizons x 2 costs x "
          "{MOM,REV} + 7 named setups x 3 x 2), NOT ONE achieved same-sign mean bps in both "
          "train and test with |day-clustered t|>=2 in both. Net of even 1bp round-trip cost, "
          "BTC derivatives-positioning signals show **no reliable out-of-sample short-horizon "
          "predictive edge** in this sample. This is a clean null.")
    P("")
    P(f"_Grid size: {len(signals)} signals x {len(HORIZONS)} horizons x {len(COSTS)} costs x 2 modes "
      f"+ {len(setups)} setups x {len(HORIZONS)} x {len(COSTS)} = "
      f"{len(signals)*len(HORIZONS)*len(COSTS)*2 + len(setups)*len(HORIZONS)*len(COSTS)} tested cells._")

    with open(REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nWrote {REPORT}", flush=True)
    print(f"SURVIVORS: {len(survivors)}", flush=True)

    # emit a compact grid to stdout for the caller
    print("\n===GRID_SUMMARY===")
    for l in lines:
        print(l)

if __name__ == "__main__":
    main()
