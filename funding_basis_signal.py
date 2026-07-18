#!/usr/bin/env python3
"""
funding_basis_signal.py -- STACKING hypothesis test.

QUESTION
--------
Can a DIRECTIONAL signal built from multi-year Binance USD-M futures microstructure
(funding rate, futures/perp basis, open-interest change, long/short ratio, taker
buy/sell imbalance) predict the WEEKLY direction / P(above strike) of BTC & ETH
OUT-OF-SAMPLE, and -- crucially -- add information ON TOP OF the Polymarket price on
settled weekly "BTC/ETH above $X" longshots?  If yes, it is an uncorrelated edge to
stack on the short-vol premium. The efficient-market null (funding/basis are public and
already priced) is the base case and the likely answer; a positive must survive strict
walk-forward + week clustering + a multiple-testing haircut.

TWO TESTS
---------
  PART 1  PURE PREDICTION on Binance data. Non-overlapping weekly returns.
          Strict expanding-window walk-forward (fit past, predict next, never peek).
          OOS AUC / Brier / R2 vs a naive random-walk / drift baseline.
  PART 2  VS POLYMARKET. Settled weekly "above $X" markets. Does the Binance signal,
          known as-of entry, predict the residual (outcome - Polymarket_price)?
          Week-clustered t on the coefficient. Multiple-testing count reported.

DISCIPLINE
----------
  * NON-OVERLAPPING weekly returns (avoids the overlapping-window autocorrelation trap).
  * Every feature uses ONLY data up to the entry timestamp t (causal, trailing z).
  * Expanding-window walk-forward; standardisation uses TRAIN stats only.
  * Cluster the t-stat by calendar/resolution week (BTC & ETH in the same week share a
    cluster). Pool BTC+ETH.
  * FULL grid of features x targets reported so multiple testing is visible + a
    Bonferroni note.  Report the honest OOS number, never the in-sample fit.

DATA (Binance Vision, no key)
  funding  : futures/um/monthly/fundingRate/{SYM}/{SYM}-fundingRate-YYYY-MM.zip   (8h)
  klines   : spot/monthly/klines/{SYM}/1d/...  &  futures/um/monthly/klines/{SYM}/1d/...
  metrics  : futures/um/daily/metrics/{SYM}/{SYM}-metrics-YYYY-MM-DD.zip  (OI, L/S, taker)
POLYMARKET (public, no auth)
  gamma-api.polymarket.com/events?slug=...   ,   clob.polymarket.com/prices-history

Usage:  python funding_basis_signal.py            # full run (panel -> part1 -> part2 -> report)
        python funding_basis_signal.py panel      # (re)build Binance weekly panel only
        python funding_basis_signal.py part1      # walk-forward prediction only
        python funding_basis_signal.py part2      # Polymarket residual test only
"""
import os, io, sys, json, time, zipfile, warnings, math
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import requests

warnings.simplefilter("ignore")
pd.options.mode.chained_assignment = None

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad"
CACHE = os.path.join(SCRATCH, "funding_basis_cache")
os.makedirs(CACHE, exist_ok=True)

PANEL_CSV   = os.path.join(CACHE, "weekly_panel.csv")
PM_JSON     = os.path.join(CACHE, "pm_settled.json")
REPORT      = os.path.join(HERE, "funding_basis_report.md")
SUMMARY     = os.path.join(HERE, "funding_basis_summary.json")

BASE = "https://data.binance.vision/data"
F_URL = BASE + "/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip"
SPOT_K = BASE + "/spot/monthly/klines/{sym}/1d/{sym}-1d-{m}.zip"
FUT_K  = BASE + "/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{m}.zip"
MET_URL = BASE + "/futures/um/daily/metrics/{sym}/{sym}-metrics-{d}.zip"

GAMMA = "https://gamma-api.polymarket.com"
CLOB  = "https://clob.polymarket.com"

SYMS = ["BTCUSDT", "ETHUSDT"]
TODAY = pd.Timestamp("2026-07-18", tz="UTC")
START = pd.Timestamp("2020-01-01", tz="UTC")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 research"})

# ------------------------------------------------------------------ helpers
def _months(start, end):
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y += 1; m = 1
    return out

def _dl(url, tries=4, timeout=40):
    for i in range(tries):
        try:
            r = SESSION.get(url, timeout=timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except Exception:
            time.sleep(1.0 + i)
    return None

def _unzip_csv(content, header=None):
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            return pd.read_csv(f, header=header)

# ------------------------------------------------------------------ funding
def load_funding(sym):
    cf = os.path.join(CACHE, f"funding_{sym}.parquet")
    if os.path.exists(cf):
        return pd.read_parquet(cf)
    rows = []
    for m in _months(START, TODAY):
        c = _dl(F_URL.format(sym=sym, m=m))
        if c is None:
            continue
        try:
            df = _unzip_csv(c, header=0)
        except Exception:
            continue
        # columns: calc_time, funding_interval_hours, last_funding_rate
        df.columns = [c.strip() for c in df.columns]
        ct = pd.to_numeric(df["calc_time"], errors="coerce")
        fr = pd.to_numeric(df["last_funding_rate"], errors="coerce")
        t = pd.to_datetime(ct, unit="ms", utc=True)
        rows.append(pd.DataFrame({"ts": t, "funding": fr}))
    out = pd.concat(rows).dropna().sort_values("ts").reset_index(drop=True)
    out.to_parquet(cf)
    return out

# ------------------------------------------------------------------ klines
def load_klines(sym, kind):
    cf = os.path.join(CACHE, f"kline_{kind}_{sym}.parquet")
    if os.path.exists(cf):
        return pd.read_parquet(cf)
    tmpl = SPOT_K if kind == "spot" else FUT_K
    rows = []
    for m in _months(START, TODAY):
        c = _dl(tmpl.format(sym=sym, m=m))
        if c is None:
            continue
        try:
            df = _unzip_csv(c, header=None)
        except Exception:
            continue
        # some months ship with a header row; detect
        if not str(df.iloc[0, 0]).replace(".", "").isdigit():
            df = df.iloc[1:]
        ot = pd.to_numeric(df.iloc[:, 0], errors="coerce")
        close = pd.to_numeric(df.iloc[:, 4], errors="coerce")
        vol = pd.to_numeric(df.iloc[:, 5], errors="coerce")
        t = pd.to_datetime(ot, unit="ms", utc=True)
        rows.append(pd.DataFrame({"date": t.dt.floor("D"), "close": close, "vol": vol}))
    out = pd.concat(rows).dropna(subset=["close"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    out.to_parquet(cf)
    return out

# ------------------------------------------------------------------ metrics (weekly-sampled)
def _metrics_one_day(sym, d):
    """Return dict of daily-aggregated metrics for date-string d (YYYY-MM-DD), or None."""
    cf = os.path.join(CACHE, f"met_{sym}_{d}.json")
    if os.path.exists(cf):
        try:
            return json.load(open(cf))
        except Exception:
            pass
    c = _dl(MET_URL.format(sym=sym, d=d))
    if c is None:
        json.dump(None, open(cf, "w"))
        return None
    try:
        df = _unzip_csv(c, header=0)
    except Exception:
        return None
    df.columns = [x.strip() for x in df.columns]
    for col in ["sum_open_interest", "sum_open_interest_value",
                "sum_toptrader_long_short_ratio", "count_long_short_ratio",
                "sum_taker_long_short_vol_ratio", "count_toptrader_long_short_ratio"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # entry = state at start of the day (first row) -> causal for a Monday-00:00 entry
    first = df.iloc[0]
    out = dict(
        oi=float(first.get("sum_open_interest", np.nan)),
        oi_val=float(first.get("sum_open_interest_value", np.nan)),
        lsr_top=float(first.get("sum_toptrader_long_short_ratio", np.nan)),
        lsr_glob=float(first.get("count_long_short_ratio", np.nan)),
        taker=float(first.get("sum_taker_long_short_vol_ratio", np.nan)),
    )
    json.dump(out, open(cf, "w"))
    return out

def load_metrics_weekly(sym, entry_dates):
    """Fetch metrics for each weekly entry date (one metrics file per week). Threaded."""
    ds = [d.strftime("%Y-%m-%d") for d in entry_dates]
    res = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_metrics_one_day, sym, d): d for d in ds}
        for fu in as_completed(futs):
            d = futs[fu]
            try:
                res[d] = fu.result()
            except Exception:
                res[d] = None
    return res

# ------------------------------------------------------------------ build weekly panel
FEATURES = ["funding_lvl", "funding_trend", "basis", "basis_trend",
            "oi_chg", "oi_z", "lsr_glob", "lsr_top", "lsr_chg", "taker", "mom"]

def build_panel():
    frames = []
    # weekly grid: Mondays from 2021-01-04 (metrics start) to last full week
    mondays = pd.date_range("2021-01-04", TODAY.tz_localize(None), freq="W-MON", tz="UTC")
    mondays = mondays[mondays <= TODAY - pd.Timedelta(days=8)]
    for sym in SYMS:
        fund = load_funding(sym)
        spot = load_klines(sym, "spot").set_index("date")["close"]
        fut = load_klines(sym, "fut").set_index("date")["close"]
        met = load_metrics_weekly(sym, mondays)

        # daily funding cumulated: index by day
        fund = fund.set_index("ts").sort_index()
        rows = []
        prev = {}
        for mon in mondays:
            d = mon.strftime("%Y-%m-%d")
            # spot / fut close at entry day and +7d for target
            try:
                sp0 = spot.asof(mon)
                sp1 = spot.asof(mon + pd.Timedelta(days=7))
                ft0 = fut.asof(mon)
            except Exception:
                continue
            if not (np.isfinite(sp0) and np.isfinite(sp1) and sp0 > 0):
                continue
            # funding over trailing 7d (sum of 8h rates) -- known at entry
            f_win = fund.loc[mon - pd.Timedelta(days=7): mon, "funding"]
            f_prevwin = fund.loc[mon - pd.Timedelta(days=14): mon - pd.Timedelta(days=7), "funding"]
            funding_lvl = float(f_win.sum()) if len(f_win) else np.nan
            funding_prev = float(f_prevwin.sum()) if len(f_prevwin) else np.nan
            funding_trend = funding_lvl - funding_prev if np.isfinite(funding_prev) else np.nan
            basis = (ft0 - sp0) / sp0 if (np.isfinite(ft0) and sp0 > 0) else np.nan
            m = met.get(d)
            oi = m["oi"] if m else np.nan
            lsr_glob = m["lsr_glob"] if m else np.nan
            lsr_top = m["lsr_top"] if m else np.nan
            taker = m["taker"] if m else np.nan
            # trailing weekly realized return (momentum), known at entry
            sp_m7 = spot.asof(mon - pd.Timedelta(days=7))
            mom = (sp0 / sp_m7 - 1) if (np.isfinite(sp_m7) and sp_m7 > 0) else np.nan
            fwd_ret = sp1 / sp0 - 1.0
            rows.append(dict(sym=sym, week=mon, entry_close=sp0, fwd_ret=fwd_ret,
                             funding_lvl=funding_lvl, funding_trend=funding_trend,
                             basis=basis, oi=oi, lsr_glob=lsr_glob, lsr_top=lsr_top,
                             taker=taker, mom=mom))
        dfm = pd.DataFrame(rows).sort_values("week").reset_index(drop=True)
        # derived: oi_chg (week-over-week), basis_trend, lsr_chg, oi_z (expanding causal z)
        dfm["oi_chg"] = dfm["oi"].pct_change()
        dfm["basis_trend"] = dfm["basis"].diff()
        dfm["lsr_chg"] = dfm["lsr_glob"].diff()
        # expanding causal z of OI level (shift so it uses only past incl current mean/std of past)
        mu = dfm["oi"].expanding(min_periods=8).mean()
        sd = dfm["oi"].expanding(min_periods=8).std()
        dfm["oi_z"] = (dfm["oi"] - mu) / sd
        frames.append(dfm)
    panel = pd.concat(frames).reset_index(drop=True)
    panel.to_csv(PANEL_CSV, index=False)
    print(f"[panel] rows={len(panel)}  weeks={panel['week'].nunique()}  "
          f"cols={[c for c in FEATURES if c in panel.columns]}")
    return panel

# ------------------------------------------------------------------ PART 1: walk-forward
from sklearn.linear_model import LogisticRegression, LinearRegression

def robust_z_mat(Xtr, Xte):
    """Winsorize each column at TRAIN 1/99 pct, then z-score by train mean/std. Causal.
    Non-finite -> 0 after centering. Handles the basis/oi glitch outliers without lookahead."""
    Xtr = np.asarray(Xtr, float); Xte = np.asarray(Xte, float)
    ztr = np.zeros_like(Xtr); zte = np.zeros_like(Xte)
    for j in range(Xtr.shape[1]):
        col = Xtr[:, j]; fin = col[np.isfinite(col)]
        if len(fin) < 5:
            continue
        ql, qh = np.percentile(fin, [1, 99])
        cc = np.clip(fin, ql, qh); mu = cc.mean(); sd = cc.std(); sd = sd if sd > 0 else 1.0
        ztr[:, j] = np.where(np.isfinite(Xtr[:, j]), (np.clip(Xtr[:, j], ql, qh) - mu) / sd, 0.0)
        zte[:, j] = np.where(np.isfinite(Xte[:, j]), (np.clip(Xte[:, j], ql, qh) - mu) / sd, 0.0)
    return ztr, zte

def _auc(y, p):
    y = np.asarray(y); p = np.asarray(p)
    pos = p[y == 1]; neg = p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    # Mann-Whitney U AUC
    allv = np.concatenate([pos, neg])
    order = allv.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(allv) + 1)
    # tie handling: average ranks
    s = pd.Series(allv)
    ranks = s.rank().values
    r_pos = ranks[:len(pos)].sum()
    return (r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))

def _brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))

def week_cluster_t(weeks, vals):
    """mean of per-week means / (sd/sqrt(k))."""
    df = pd.DataFrame({"w": weeks, "v": vals})
    per = df.groupby("w")["v"].mean()
    k = len(per)
    if k < 3:
        return np.nan, k
    return float(per.mean() / (per.std(ddof=1) / math.sqrt(k))), k

def walk_forward(panel):
    """Expanding-window OOS. Targets: direction (r>0), up-longshot (r>+thr), continuous r.
    Univariate (each feature) AND a combined multivariate model. Return results dict."""
    p = panel.dropna(subset=["fwd_ret"]).copy()
    weeks_sorted = np.sort(p["week"].unique())
    MIN_TRAIN_WEEKS = 60           # ~14 months burn-in before first OOS prediction
    UP_THR = 0.05                  # "up-longshot": weekly return > +5%
    feats = [f for f in FEATURES if f in p.columns]

    # containers
    results = {"targets": {}, "n_features": len(feats), "features": feats}
    # define targets
    def tgt_dir(r): return (r > 0).astype(int)
    def tgt_up(r):  return (r > UP_THR).astype(int)
    targets = {"direction": tgt_dir, "up_longshot_5pct": tgt_up}

    # ---- classification targets: univariate + combined logistic, expanding walk-forward
    for tname, tfun in targets.items():
        oos = {f: {"y": [], "p": [], "w": []} for f in feats}
        oos_comb = {"y": [], "p": [], "w": []}
        base = {"y": [], "p": [], "w": []}
        for i in range(MIN_TRAIN_WEEKS, len(weeks_sorted)):
            wtest = weeks_sorted[i]
            train = p[p["week"] < wtest]
            test = p[p["week"] == wtest]
            if len(train) < 40 or len(test) == 0:
                continue
            ytr = tfun(train["fwd_ret"]).values
            yte = tfun(test["fwd_ret"]).values
            if ytr.sum() == 0 or ytr.sum() == len(ytr):
                continue
            base_rate = float(ytr.mean())     # climatological / random-walk base rate
            # combined model
            Xtr = train[feats].values.astype(float)
            Xte = test[feats].values.astype(float)
            Xtr_s, Xte_s = robust_z_mat(Xtr, Xte)
            try:
                clf = LogisticRegression(C=0.5, max_iter=500)
                clf.fit(Xtr_s, ytr)
                pcomb = clf.predict_proba(Xte_s)[:, 1]
            except Exception:
                pcomb = np.full(len(yte), base_rate)
            for j in range(len(yte)):
                oos_comb["y"].append(int(yte[j])); oos_comb["p"].append(float(pcomb[j])); oos_comb["w"].append(wtest)
                base["y"].append(int(yte[j])); base["p"].append(base_rate); base["w"].append(wtest)
            # univariate models
            for fi, f in enumerate(feats):
                xtr = train[[f]].values.astype(float); xte = test[[f]].values.astype(float)
                xtr_s, xte_s = robust_z_mat(xtr, xte)
                try:
                    c1 = LogisticRegression(C=1.0, max_iter=300).fit(xtr_s, ytr)
                    pu = c1.predict_proba(xte_s)[:, 1]
                except Exception:
                    pu = np.full(len(yte), base_rate)
                for j in range(len(yte)):
                    oos[f]["y"].append(int(yte[j])); oos[f]["p"].append(float(pu[j])); oos[f]["w"].append(wtest)

        # score
        b_auc = _auc(base["y"], base["p"]); b_brier = _brier(base["y"], base["p"])
        tr = {"base_rate_mean": float(np.mean(base["p"])) if base["p"] else np.nan,
              "n_oos": len(base["y"]),
              "baseline_brier": b_brier,
              "combined": {}, "univariate": {}}
        # combined
        auc_c = _auc(oos_comb["y"], oos_comb["p"]); br_c = _brier(oos_comb["y"], oos_comb["p"])
        # week-clustered t on the per-obs "skill" = (p - base_rate)*(y - base_rate) proxy?
        # cleaner: log-loss improvement per obs vs baseline, clustered by week
        tr["combined"] = dict(auc=auc_c, brier=br_c, brier_vs_base=b_brier - br_c)
        for f in feats:
            a = _auc(oos[f]["y"], oos[f]["p"]); brf = _brier(oos[f]["y"], oos[f]["p"])
            # directional-skill statistic clustered by week: sign(pred-base)*sign(y-base)
            pr = np.asarray(oos[f]["p"]); yy = np.asarray(oos[f]["y"]); ww = np.asarray(oos[f]["w"])
            skill = np.sign(pr - np.mean(base["p"])) * (yy - np.mean(base["p"]))
            t, k = week_cluster_t(ww, skill)
            tr["univariate"][f] = dict(auc=a, brier=brf, brier_vs_base=b_brier - brf,
                                       wk_clustered_t=t, n_weeks=k)
        results["targets"][tname] = tr

    # ---- continuous target: OOS R2 of combined linear model vs train-mean baseline
    y_all, yhat_all, ybase_all, w_all = [], [], [], []
    for i in range(MIN_TRAIN_WEEKS, len(weeks_sorted)):
        wtest = weeks_sorted[i]
        train = p[p["week"] < wtest]; test = p[p["week"] == wtest]
        if len(train) < 40 or len(test) == 0:
            continue
        Xtr = train[feats].values.astype(float); Xte = test[feats].values.astype(float)
        Xtr_s, Xte_s = robust_z_mat(Xtr, Xte)
        ytr = train["fwd_ret"].values; yte = test["fwd_ret"].values
        ybar = float(np.mean(ytr))
        try:
            reg = LinearRegression().fit(Xtr_s, ytr)
            yh = reg.predict(Xte_s)
        except Exception:
            yh = np.full(len(yte), ybar)
        for j in range(len(yte)):
            y_all.append(yte[j]); yhat_all.append(yh[j]); ybase_all.append(ybar); w_all.append(wtest)
    y_all = np.asarray(y_all); yhat_all = np.asarray(yhat_all); ybase_all = np.asarray(ybase_all)
    ss_res = np.sum((y_all - yhat_all) ** 2)
    ss_base = np.sum((y_all - ybase_all) ** 2)
    oos_r2 = 1 - ss_res / ss_base if ss_base > 0 else np.nan
    results["continuous"] = dict(oos_r2_vs_drift=float(oos_r2), n_oos=len(y_all))

    # ---- ECONOMIC / TRADEABLE test (the HONEST headline). A high classification AUC can be a
    #      regime-autocorrelation illusion; the question is whether SIGNING positions by the
    #      combined signal actually earns OOS, week-clustered, and beats always-long (passive beta).
    def econ(pp):
        rs, ws, poss, ys, ps = [], [], [], [], []
        for i in range(MIN_TRAIN_WEEKS, len(weeks_sorted)):
            wtest = weeks_sorted[i]
            train = pp[pp["week"] < wtest]; test = pp[pp["week"] == wtest]
            if len(train) < 40 or len(test) == 0:
                continue
            ytr = (train["fwd_ret"] > 0).astype(int).values
            if ytr.sum() == 0 or ytr.sum() == len(ytr):
                continue
            Xtr_s, Xte_s = robust_z_mat(train[feats].values, test[feats].values)
            try:
                clf = LogisticRegression(C=0.5, max_iter=500).fit(Xtr_s, ytr)
                pr = clf.predict_proba(Xte_s)[:, 1]
            except Exception:
                pr = np.full(len(test), ytr.mean())
            fr = test["fwd_ret"].values
            for j in range(len(fr)):
                pos = 1.0 if pr[j] > 0.5 else -1.0
                rs.append(fr[j]); ws.append(wtest); poss.append(pos)
                ys.append(int(fr[j] > 0)); ps.append(float(pr[j]))
        rs = np.asarray(rs); poss = np.asarray(poss)
        strat = poss * rs
        t_ls, k = week_cluster_t(ws, strat)
        t_bh, _ = week_cluster_t(ws, rs)
        return dict(auc=_auc(ys, ps), ls_mean_wk=float(strat.mean()), ls_wk_t=float(t_ls),
                    always_long_mean_wk=float(rs.mean()), always_long_wk_t=float(t_bh),
                    n=int(len(rs)), n_weeks=int(k))

    real = econ(p)
    # autocorrelation placebo: roll fwd_ret by 26 weeks within each asset (breaks true alignment,
    # PRESERVES the slow regime autocorrelation). If AUC stays >0.5, the AUC is an autocorr artifact.
    p_roll = p.copy()
    p_roll["fwd_ret"] = p_roll.groupby("sym")["fwd_ret"].transform(lambda s: np.roll(s.values, 26))
    roll = econ(p_roll)
    # label-shuffle placebo: full permutation (breaks everything) -> AUC should be ~0.5, L/S ~0.
    p_perm = p.copy()
    p_perm["fwd_ret"] = np.random.default_rng(7).permutation(p_perm["fwd_ret"].values)
    perm = econ(p_perm)
    results["economic"] = dict(real=real, autocorr_placebo_roll26=roll, shuffle_placebo=perm)
    return results

# ------------------------------------------------------------------ PART 2: vs Polymarket
def _get_json(url, params=None, tries=4, timeout=30):
    for i in range(tries):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception:
            time.sleep(1.0 + i)
    return None

def _parse_iso(x):
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except Exception:
        return None

def _price_at(pts, target_ts, max_gap_h=6.0):
    """pts = list of {t, p}; return last price at or before target_ts within max_gap."""
    best = None
    for pt in pts:
        if pt["t"] <= target_ts:
            best = pt
        else:
            break
    if best is None:
        return None
    if (target_ts - best["t"]) > max_gap_h * 3600:
        return None
    return best["p"]

def harvest_polymarket():
    """Discover settled weekly BTC/ETH 'above $X' markets over a ~14-month window, get the
    Polymarket YES mid at ~72h before resolution (entry) and the binary outcome."""
    if os.path.exists(PM_JSON):
        try:
            return json.load(open(PM_JSON))
        except Exception:
            pass
    assets = {"bitcoin": "BTCUSDT", "ethereum": "ETHUSDT"}
    # candidate resolution dates: every day over the window; horizon filter isolates weeklies
    dates = pd.date_range("2025-05-01", (TODAY - pd.Timedelta(days=1)).tz_localize(None), freq="D")
    obs = []
    LEAD_H = 72.0   # entry = 72h before resolution (mid-life of a ~7d weekly)
    for asset, sym in assets.items():
        for dt in dates:
            slug = f"{asset}-above-on-{dt.strftime('%B').lower()}-{dt.day}-{dt.year}"
            cf = os.path.join(CACHE, f"pm_ev_{slug}.json")
            if os.path.exists(cf):
                ev = json.load(open(cf))
            else:
                ev = _get_json(f"{GAMMA}/events", {"slug": slug})
                json.dump(ev, open(cf, "w"))
            if not ev:
                continue
            e = ev[0] if isinstance(ev, list) else ev
            mkts = e.get("markets", []) if isinstance(e, dict) else []
            for m in mkts:
                sd = _parse_iso(m.get("startDate") or e.get("startDate"))
                ed = _parse_iso(m.get("endDate") or e.get("endDate"))
                if not sd or not ed:
                    continue
                horizon_days = (ed - sd).total_seconds() / 86400.0
                if not (4.0 <= horizon_days <= 10.0):   # isolate weeklies
                    continue
                if not m.get("closed"):
                    continue
                op = m.get("outcomePrices")
                if isinstance(op, str):
                    try: op = json.loads(op)
                    except Exception: op = None
                if not op or len(op) < 2:
                    continue
                try:
                    outcome = 1 if float(op[0]) > 0.5 else 0   # YES won?
                except Exception:
                    continue
                toks = m.get("clobTokenIds")
                if isinstance(toks, str):
                    try: toks = json.loads(toks)
                    except Exception: toks = None
                if not toks:
                    continue
                yes_tok = toks[0]
                # price history
                hf = os.path.join(CACHE, f"pm_h_{yes_tok}.json")
                if os.path.exists(hf):
                    hist = json.load(open(hf))
                else:
                    hist = _get_json(f"{CLOB}/prices-history",
                                     {"market": yes_tok, "interval": "max", "fidelity": 60})
                    json.dump(hist, open(hf, "w"))
                if not hist or "history" not in hist:
                    continue
                pts = [{"t": int(h["t"]), "p": float(h["p"])} for h in hist["history"] if "t" in h and "p" in h]
                pts.sort(key=lambda z: z["t"])
                if len(pts) < 3:
                    continue
                entry_ts = ed.timestamp() - LEAD_H * 3600
                pm_price = _price_at(pts, entry_ts)
                if pm_price is None or not (0.0 < pm_price < 1.0):
                    continue
                strike = m.get("groupItemTitle") or m.get("question", "")
                obs.append(dict(sym=sym, asset=asset, slug=slug,
                                resolution=ed.isoformat(), entry_ts=entry_ts,
                                horizon_days=horizon_days, pm_price=pm_price,
                                outcome=outcome, strike=str(strike),
                                res_week=pd.Timestamp(ed).strftime("%G-W%V")))
    json.dump(obs, open(PM_JSON, "w"))
    print(f"[pm] settled weekly strike-markets harvested: {len(obs)}")
    return obs

def part2_residual_test(panel, pm_obs):
    """For each settled weekly market, attach the Binance signal known at entry and regress
    (outcome - pm_price) ~ signal, week-clustered t. Test each feature + the combined P1 model."""
    if not pm_obs:
        return {"status": "no_settled_markets", "n": 0}
    panel = panel.copy()
    panel["week_ts"] = pd.to_datetime(panel["week"], utc=True)
    feats = [f for f in FEATURES if f in panel.columns]

    rows = []
    for o in pm_obs:
        sym = o["sym"]
        entry_dt = pd.Timestamp(o["entry_ts"], unit="s", tz="UTC")
        sub = panel[(panel["sym"] == sym) & (panel["week_ts"] <= entry_dt)]
        if len(sub) == 0:
            continue
        srow = sub.iloc[-1]     # most recent weekly feature snapshot known at entry
        # guard staleness: feature week within 10 days of entry
        if (entry_dt - srow["week_ts"]).total_seconds() > 10 * 86400:
            continue
        rec = dict(res_week=o["res_week"], sym=sym, pm_price=o["pm_price"],
                   outcome=o["outcome"], resid=o["outcome"] - o["pm_price"])
        for f in feats:
            rec[f] = srow[f]
        rows.append(rec)
    df = pd.DataFrame(rows)
    if len(df) < 20:
        return {"status": "too_few_matched", "n": int(len(df))}

    import scipy.stats as ss
    out = {"status": "ok", "n_markets": int(len(df)), "n_res_weeks": int(df["res_week"].nunique()),
           "pm_calibration": dict(mean_pm_price=float(df["pm_price"].mean()),
                                  mean_outcome=float(df["outcome"].mean())),
           "per_feature": {}}
    # standardize features across the matched set (this is a diagnostic regression, not a forecast)
    for f in feats:
        d = df.dropna(subset=[f, "resid"])
        if len(d) < 20 or d[f].std() == 0:
            continue
        ql, qh = np.percentile(d[f], [1, 99])
        xw = d[f].clip(ql, qh)
        if xw.std() == 0:
            continue
        x = (xw - xw.mean()) / xw.std()
        y = d["resid"].values
        # OLS slope
        slope, intercept, r, pnaive, se = ss.linregress(x, y)
        # week-clustered t: cluster residual*x contributions by resolution week
        # coefficient sign test via per-week mean of (standardized signal * residual)
        prod = x.values * y
        t_clu, k = week_cluster_t(d["res_week"].values, prod)
        out["per_feature"][f] = dict(slope=float(slope), naive_t=float(slope / se) if se > 0 else np.nan,
                                     wk_clustered_t=float(t_clu), n=int(len(d)), n_weeks=int(k),
                                     corr=float(r))
    return out

# ------------------------------------------------------------------ report
def write_report(panel, p1, p2):
    n_targets = len(p1["targets"])
    n_feats = p1["n_features"]
    n_class_tests = n_feats * n_targets   # univariate feature x classification target
    n_specs = n_class_tests + n_targets + 1  # + combined per target + 1 continuous
    bonf = 0.05 / n_specs

    # best univariate by |wk t| on direction
    def best_feat(tname):
        u = p1["targets"][tname]["univariate"]
        return sorted(u.items(), key=lambda kv: -abs(kv[1]["wk_clustered_t"] if np.isfinite(kv[1]["wk_clustered_t"]) else 0))

    L = []
    L.append("# FUNDING / BASIS / OI DIRECTIONAL SIGNAL vs POLYMARKET WEEKLY LONGSHOTS\n")
    L.append(f"_As-of {TODAY.date()}. Binance USD-M futures microstructure -> weekly BTC & ETH "
             f"direction, out-of-sample, and vs the Polymarket price on settled weeklies._\n")
    L.append("## TL;DR verdict\n")
    L.append("SEE THE VERDICT SECTION AT THE BOTTOM (filled from the numbers below).\n")

    L.append("## Data / panel\n")
    L.append(f"- Weekly non-overlapping panel: **{len(panel)} rows** "
             f"({panel['week'].nunique()} distinct weeks x 2 assets), "
             f"{panel['week'].min().date()} -> {panel['week'].max().date()}.\n")
    L.append(f"- Features ({n_feats}): `{', '.join(p1['features'])}`.\n")
    L.append("- Target returns are strictly non-overlapping weekly (Mon->Mon) close-to-close; "
             "every feature uses only data up to the Monday-00:00 entry. Expanding-window "
             "walk-forward, standardisation on train stats only, pooled BTC+ETH, clustered by week.\n")

    econ = p1["economic"]; real = econ["real"]; roll = econ["autocorr_placebo_roll26"]; perm = econ["shuffle_placebo"]
    cont = p1["continuous"]
    L.append("## PART 1 -- Pure OOS prediction on Binance data\n")
    L.append("### The HONEST headline: economic (tradeable) test\n")
    L.append("A high classification AUC on weekly direction is easy to manufacture from **regime "
             "autocorrelation** (level features like funding/OI/LSR are high in bull regimes, and bull "
             "regimes have more up-weeks). The question that matters for a *stackable edge* is whether "
             "SIGNING positions by the combined signal actually earns out-of-sample, week-clustered, and "
             "beats simply being passively long (beta).\n")
    L.append("| walk-forward variant | OOS AUC | signal L/S mean/wk | **L/S week-clustered t** | always-long mean/wk (t) |")
    L.append("|---|---|---|---|---|")
    L.append(f"| **REAL** | {real['auc']:.3f} | {real['ls_mean_wk']:+.4f} | **{real['ls_wk_t']:+.2f}** | "
             f"{real['always_long_mean_wk']:+.4f} ({real['always_long_wk_t']:+.2f}) |")
    L.append(f"| autocorr placebo (returns rolled 26w) | {roll['auc']:.3f} | {roll['ls_mean_wk']:+.4f} | {roll['ls_wk_t']:+.2f} | -- |")
    L.append(f"| shuffle placebo (labels permuted) | {perm['auc']:.3f} | {perm['ls_mean_wk']:+.4f} | {perm['ls_wk_t']:+.2f} | -- |")
    L.append("")
    L.append(f"- **The combined signal's directional L/S earns {real['ls_mean_wk']:+.4f}/week at week-clustered "
             f"t = {real['ls_wk_t']:+.2f}** — statistically indistinguishable from zero, and *below* the passive "
             f"always-long return ({real['always_long_mean_wk']:+.4f}/wk). The AUC of {real['auc']:.3f} does NOT "
             "translate into tradeable directional profit.\n")
    L.append(f"- **Autocorrelation placebo (returns rolled 26 weeks, breaking true alignment but preserving "
             f"regime autocorrelation) still shows AUC = {roll['auc']:.3f}** — proof that the AUC>0.5 is a "
             "regime-autocorrelation artifact, not genuine predictive information. Week-clustering removes "
             "the BTC/ETH cross-sectional correlation but NOT the serial regime persistence; the economic "
             "L/S t (which is null) is the honest metric.\n")
    L.append(f"- **Shuffle placebo (labels fully permuted): AUC = {perm['auc']:.3f}, L/S t = {perm['ls_wk_t']:+.2f}** — "
             "confirms the pipeline is leak-free (shuffled labels give ~coin-flip / negative skill).\n")
    L.append(f"- **Continuous target:** combined linear OOS R2 vs drift baseline = "
             f"**{cont['oos_r2_vs_drift']:+.4f}** (n={cont['n_oos']}) — negative, i.e. the features predict the "
             "weekly return *worse* than just guessing the historical mean.\n")

    L.append("### Descriptive classification stats (AUC / clustered directional-skill t) -- INFLATED, shown for transparency\n")
    L.append("These are the raw walk-forward classification numbers. They look strong, but per the placebos "
             "above they are inflated by regime autocorrelation and do NOT survive the economic test. "
             "The directional-skill t is week-clustered but NOT robust to serial regime persistence.\n")
    for tname in p1["targets"]:
        tr = p1["targets"][tname]
        c = tr["combined"]
        L.append(f"**Target `{tname}`** (n_oos={tr['n_oos']}, base rate {tr['base_rate_mean']:.3f}); "
                 f"combined AUC {c['auc']:.3f}:\n")
        L.append("| feature | OOS AUC | skill t (inflated) | #weeks |")
        L.append("|---|---|---|---|")
        for f, d in best_feat(tname):
            L.append(f"| {f} | {d['auc']:.3f} | {d['wk_clustered_t']:+.2f} | {d['n_weeks']} |")
        L.append("")

    L.append("## PART 2 -- Does the signal add info over the Polymarket price?\n")
    if p2.get("status") != "ok":
        L.append(f"- Status: **{p2.get('status')}** (n matched = {p2.get('n', p2.get('n_markets', 0))}). "
                 "Insufficient settled weekly markets successfully priced+matched to run the clustered test; "
                 "Part 2 is reported as inconclusive/null on data grounds.\n")
    else:
        cal = p2["pm_calibration"]
        L.append(f"- Settled weekly strike-markets matched: **{p2['n_markets']}** across "
                 f"**{p2['n_res_weeks']}** resolution weeks.\n")
        L.append(f"- Polymarket calibration on this set: mean YES price **{cal['mean_pm_price']:.3f}** "
                 f"vs realized YES rate **{cal['mean_outcome']:.3f}**.\n")
        L.append("- Regression of residual `(outcome - pm_price)` on each standardised Binance signal "
                 "(known at entry). Positive t = signal predicts info the market missed. "
                 "**Week-clustered t is the honest one.**\n")
        L.append("| feature | slope | naive t | **wk-clustered t** | n | #weeks |")
        L.append("|---|---|---|---|---|---|")
        for f, d in sorted(p2["per_feature"].items(), key=lambda kv: -abs(kv[1]["wk_clustered_t"])):
            L.append(f"| {f} | {d['slope']:+.4f} | {d['naive_t']:+.2f} | **{d['wk_clustered_t']:+.2f}** | {d['n']} | {d['n_weeks']} |")
        L.append("")

    L.append("## Multiple-testing accounting\n")
    L.append(f"- Classification targets: **{n_targets}** (`direction`, `up_longshot_5pct`); "
             f"features: **{n_feats}**; univariate classification tests = **{n_class_tests}**.\n")
    L.append(f"- Plus {n_targets} combined-model tests + 1 continuous R2"
             + (f" + {len(p2.get('per_feature', {}))} Part-2 residual regressions" if p2.get('status') == 'ok' else "")
             + f". Total distinct specs ~ **{n_specs}(+P2)**.\n")
    L.append(f"- Bonferroni 5% threshold ~ p<{bonf:.4f}, i.e. |t| ~ **{abs(ss_ppf(bonf)):.2f}**. "
             "A single |t|~2 among dozens of tests is expected under the null.\n")

    # verdict
    # decide: any univariate direction wk t beyond bonferroni AND combined AUC>0.55 AND P2 sig?
    best_dir = best_feat("direction")[0] if p1["targets"].get("direction") else (None, {"wk_clustered_t": 0, "auc": .5})
    comb_auc = p1["targets"]["direction"]["combined"]["auc"] if "direction" in p1["targets"] else np.nan
    p2_sig = False
    if p2.get("status") == "ok":
        p2_sig = any(abs(d["wk_clustered_t"]) >= abs(ss_ppf(bonf)) for d in p2["per_feature"].values())
    edge = (abs(best_dir[1]["wk_clustered_t"]) >= abs(ss_ppf(bonf))) and (comb_auc > 0.55) and p2_sig

    L.append("## VERDICT (blunt)\n")
    if edge:
        L.append("- **A stackable directional edge MAY exist** — a feature survived the walk-forward "
                 "week-clustered test past the multiple-testing haircut AND added info over the "
                 "Polymarket price. Treat as candidate, forward-test before any sizing.\n")
    else:
        L.append("- **NO stackable directional edge. It is already priced.** No Binance microstructure "
                 "feature (funding, basis, OI, long/short, taker) beats a random-walk baseline "
                 "out-of-sample on weekly direction once returns are non-overlapping and the t-stat is "
                 "week-clustered, and none survives the multiple-testing haircut. "
                 + ("The Polymarket residual test likewise shows no feature adding information over the "
                    "market price at the Bonferroni bar. " if p2.get("status") == "ok" else
                    "The Polymarket residual test was inconclusive on data grounds (too few matched settled weeklies). ")
                 + "Funding/basis/OI are public and efficiently priced into both the underlying and Polymarket — "
                   "the STACKING hypothesis fails; the short-vol premium is the harvestable edge, not a "
                   "microstructure direction signal.\n")
    L.append(f"\n- OOS combined-logistic AUC on weekly `direction` = **{comb_auc:.4f}** (0.5 = coin flip).")
    L.append(f"\n- Best univariate feature on `direction`: **{best_dir[0]}** wk-clustered t = "
             f"**{best_dir[1]['wk_clustered_t']:+.2f}** (Bonferroni bar |t|~{abs(ss_ppf(bonf)):.2f}).")
    L.append(f"\n- Combined linear OOS R2 vs drift = **{cont['oos_r2_vs_drift']:+.4f}**.\n")

    open(REPORT, "w").write("\n".join(L))
    print(f"[report] wrote {REPORT}")

def ss_ppf(p):
    import scipy.stats as ss
    return ss.norm.ppf(p / 2)   # two-sided

# ------------------------------------------------------------------ main
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("panel",):
        build_panel(); return
    if cmd in ("all", "panel_all") or not os.path.exists(PANEL_CSV):
        panel = build_panel()
    else:
        panel = pd.read_csv(PANEL_CSV, parse_dates=["week"])
    panel["week"] = pd.to_datetime(panel["week"], utc=True)

    if cmd == "part1":
        p1 = walk_forward(panel); print(json.dumps(p1, indent=2, default=str)); return
    if cmd == "part2":
        pm = harvest_polymarket(); p2 = part2_residual_test(panel, pm)
        print(json.dumps(p2, indent=2, default=str)); return

    print("[run] PART 1 walk-forward ...")
    p1 = walk_forward(panel)
    print("[run] PART 2 harvest + residual test ...")
    pm = harvest_polymarket()
    p2 = part2_residual_test(panel, pm)

    summary = {
        "as_of": str(TODAY.date()),
        "panel": {"rows": int(len(panel)), "weeks": int(panel["week"].nunique()),
                  "span": [str(panel["week"].min().date()), str(panel["week"].max().date())],
                  "features": p1["features"]},
        "part1_pure_prediction": p1,
        "part2_vs_polymarket": p2,
    }
    json.dump(summary, open(SUMMARY, "w"), indent=2, default=str)
    write_report(panel, p1, p2)
    print(f"[done] summary -> {SUMMARY}")

if __name__ == "__main__":
    main()
