#!/usr/bin/env python3
"""
BTC order-flow (signed trade imbalance) short-horizon predictability backtest.

Question: does signed order-flow imbalance (OFI) have out-of-sample, cost-surviving
predictive power for short-horizon BTC spot returns, across multiple years/regimes?

Design (strictly causal):
  - Download one day of Binance spot aggTrades at a time, aggregate to 1-min bars
    IN MEMORY, write only the tiny bars to disk, delete the raw zip/csv immediately.
  - Signing rule: isBuyerMaker==True  -> aggressor SOLD  -> signed = -qty
                  isBuyerMaker==False -> aggressor BOUGHT -> signed = +qty
  - Per-minute bar: OFI = sum(signed qty), price = last trade price, vol = sum(qty).
  - Features S_L, L in {1,2,3,5}: base_L = trailing-L-min sum of OFI (uses bars <= t);
    denom = trailing 60-min median of |base_L|; S_L = base_L / denom. Scale-free, causal.
  - Targets ret_H, H in {1,3,5,15}: log(price[t+H]/price[t]). Future only, no overlap.
  - Bars never cross a day boundary (each day processed independently) so no cross-day leak.

Tests (full grid, no cherry-picking):
  - corr(S_L, ret_H) and sign-hit rate
  - MOMENTUM rule: long if S_L>=+Z, short if S_L<=-Z, hold H min; PnL_bps = dir*ret_H*1e4 - cost
  - REVERSION rule: trade opposite the sign of S_L
  - Z = 1.0 fixed; costs = {1bp, 5bp} round-trip
  - TRAIN = earliest 70% of sampled days, TEST = most recent 30%
  - Day-clustered t = mean(per-day mean bps) / (std(per-day mean bps)/sqrt(n_days))
"""
import os, io, sys, time, zipfile, warnings
import numpy as np
import pandas as pd
import requests

warnings.simplefilter("ignore")

SCRATCH = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad"
BARS_DIR = os.path.join(SCRATCH, "bars")
RAW_DIR = os.path.join(SCRATCH, "raw")
os.makedirs(BARS_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

BASE = "https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip"
TODAY = pd.Timestamp("2026-07-15")

Ls = [1, 2, 3, 5]
Hs = [1, 3, 5, 15]
COSTS = [1.0, 5.0]   # bps round trip
Z = 1.0

# ------------------------------------------------------------------ sampling
def sample_dates():
    dates = []
    for year in range(2022, 2027):
        for month in range(1, 13):
            for day in (1, 11, 21):
                try:
                    ts = pd.Timestamp(year=year, month=month, day=day)
                except ValueError:
                    continue
                if ts <= TODAY:
                    dates.append(ts.strftime("%Y-%m-%d"))
    return dates

# ------------------------------------------------------------------ download + aggregate one day
def process_day(dstr, session):
    out = os.path.join(BARS_DIR, f"{dstr}.parquet")
    if os.path.exists(out):
        return "cached"
    url = BASE.format(d=dstr)
    zpath = os.path.join(RAW_DIR, f"{dstr}.zip")
    try:
        r = session.get(url, timeout=180)
    except Exception as e:
        return f"err_download:{e}"
    if r.status_code == 404:
        return "404"
    if r.status_code != 200:
        return f"http_{r.status_code}"
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            name = z.namelist()[0]
            raw = z.read(name)
    except Exception as e:
        return f"err_unzip:{e}"
    del r
    # detect header
    head = raw[:200].decode("utf-8", "ignore").lower()
    header = 0 if "price" in head else None
    cols = ["aggId", "price", "qty", "f", "l", "ts", "isBuyerMaker", "isBest"]
    try:
        df = pd.read_csv(io.BytesIO(raw), header=header, names=cols,
                         usecols=["price", "qty", "ts", "isBuyerMaker"])
    except Exception as e:
        del raw
        return f"err_parse:{e}"
    del raw
    if len(df) == 0:
        return "empty"
    # signed flow
    ibm = df["isBuyerMaker"]
    if ibm.dtype != bool:
        ibm = ibm.astype(str).str.lower().isin(["true", "1"])
    signed = np.where(ibm.to_numpy(), -df["qty"].to_numpy(), df["qty"].to_numpy())
    minute = (df["ts"].to_numpy() // 60000).astype(np.int64)
    price = df["price"].to_numpy()
    qty = df["qty"].to_numpy()

    g = pd.DataFrame({"minute": minute, "signed": signed, "price": price, "qty": qty})
    agg = g.groupby("minute").agg(ofi=("signed", "sum"),
                                  price=("price", "last"),
                                  vol=("qty", "sum"))
    # reindex to full contiguous minute range within the day; empty minutes -> ofi 0, ffill price
    full = pd.RangeIndex(agg.index.min(), agg.index.max() + 1)
    agg = agg.reindex(full)
    agg["ofi"] = agg["ofi"].fillna(0.0)
    agg["vol"] = agg["vol"].fillna(0.0)
    agg["price"] = agg["price"].ffill()
    agg["day"] = dstr
    agg = agg.reset_index().rename(columns={"index": "minute"})
    agg.to_parquet(out, index=False)
    del df, g, agg
    return "ok"

# ------------------------------------------------------------------ feature build (per day, causal)
def build_features(bars):
    """bars: DataFrame for ONE day, sorted by minute. Returns feature/target frame."""
    b = bars.sort_values("minute").reset_index(drop=True)
    ofi = b["ofi"]
    price = b["price"]
    out = {"day": b["day"], "minute": b["minute"], "price": price}
    for L in Ls:
        base = ofi.rolling(L, min_periods=L).sum()
        denom = base.abs().rolling(60, min_periods=20).median()
        S = base / denom.replace(0.0, np.nan)
        out[f"S{L}"] = S
    lp = np.log(price)
    for H in Hs:
        out[f"ret{H}"] = lp.shift(-H) - lp
    return pd.DataFrame(out)

# ------------------------------------------------------------------ stats helpers
def day_clustered_t(sub, bps_col, day_col="day"):
    """t = mean(per-day mean bps)/(std(per-day mean bps)/sqrt(n_days))."""
    dm = sub.groupby(day_col)[bps_col].mean()
    n = dm.shape[0]
    if n < 2:
        return np.nan, n
    sd = dm.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return np.nan, n
    return dm.mean() / (sd / np.sqrt(n)), n

def rule_stats(df, Scol, retcol, cost, side):
    """side=+1 momentum, -1 reversion. Returns dict of stats over rows where |S|>=Z."""
    d = df[[ "day", Scol, retcol]].dropna()
    sig = np.where(d[Scol] >= Z, 1, np.where(d[Scol] <= -Z, -1, 0))
    mask = sig != 0
    d = d.loc[mask].copy()
    if len(d) == 0:
        return {"n": 0, "mean_bps": np.nan, "t": np.nan, "n_days": 0}
    direction = side * sig[mask]
    d["bps"] = direction * d[retcol].to_numpy() * 1e4 - cost
    t, ndays = day_clustered_t(d, "bps")
    return {"n": int(len(d)), "mean_bps": float(d["bps"].mean()), "t": float(t) if t == t else np.nan,
            "n_days": int(ndays)}

# ------------------------------------------------------------------ main
def main():
    dates = sample_dates()
    print(f"[sample] {len(dates)} candidate dates {dates[0]}..{dates[-1]}", flush=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "backtest/1.0"})
    got, missing = [], []
    t0 = time.time()
    for i, dstr in enumerate(dates):
        res = process_day(dstr, session)
        if res in ("ok", "cached"):
            got.append(dstr)
        else:
            missing.append((dstr, res))
        if i % 10 == 0 or res not in ("ok", "cached"):
            print(f"[{i+1}/{len(dates)}] {dstr} -> {res}  (got={len(got)}, {time.time()-t0:.0f}s)", flush=True)
    print(f"[download done] got={len(got)} missing={len(missing)} in {time.time()-t0:.0f}s", flush=True)
    for d, r in missing:
        print("   miss", d, r, flush=True)

    # -------- load all bars, build features per day
    feats = []
    for dstr in got:
        p = os.path.join(BARS_DIR, f"{dstr}.parquet")
        try:
            bars = pd.read_parquet(p)
        except Exception as e:
            print("read fail", dstr, e, flush=True)
            continue
        feats.append(build_features(bars))
    allf = pd.concat(feats, ignore_index=True)
    print(f"[features] rows={len(allf)} days={allf['day'].nunique()}", flush=True)

    # -------- train/test split by day (earliest 70% / recent 30%)
    days_sorted = sorted(allf["day"].unique())
    ntr = int(round(len(days_sorted) * 0.70))
    train_days = set(days_sorted[:ntr])
    test_days = set(days_sorted[ntr:])
    tr = allf[allf["day"].isin(train_days)]
    te = allf[allf["day"].isin(test_days)]
    print(f"[split] train_days={len(train_days)} ({days_sorted[0]}..{days_sorted[ntr-1]}) "
          f"test_days={len(test_days)} ({days_sorted[ntr]}..{days_sorted[-1]})", flush=True)

    # -------- correlation / sign-hit grid
    corr_rows = []
    for split_name, dd in [("TRAIN", tr), ("TEST", te)]:
        for L in Ls:
            for H in Hs:
                s = dd[[f"S{L}", f"ret{H}"]].dropna()
                if len(s) < 10:
                    corr_rows.append((split_name, L, H, np.nan, np.nan, len(s)))
                    continue
                c = np.corrcoef(s[f"S{L}"], s[f"ret{H}"])[0, 1]
                # sign hit of momentum (sign S == sign ret)
                hit = (np.sign(s[f"S{L}"]) == np.sign(s[f"ret{H}"])).mean()
                corr_rows.append((split_name, L, H, c, hit, len(s)))
    corr_df = pd.DataFrame(corr_rows, columns=["split", "L", "H", "corr", "signhit_mom", "n"])

    # -------- rule grid
    rows = []
    for rule, side in [("MOM", 1), ("REV", -1)]:
        for split_name, dd in [("TRAIN", tr), ("TEST", te)]:
            for L in Ls:
                for H in Hs:
                    for cost in COSTS:
                        st = rule_stats(dd, f"S{L}", f"ret{H}", cost, side)
                        rows.append((rule, split_name, L, H, cost,
                                     st["mean_bps"], st["t"], st["n"], st["n_days"]))
    grid = pd.DataFrame(rows, columns=["rule", "split", "L", "H", "cost",
                                       "mean_bps", "t", "n", "n_days"])

    # save machine-readable
    corr_df.to_csv(os.path.join(SCRATCH, "corr_grid.csv"), index=False)
    grid.to_csv(os.path.join(SCRATCH, "rule_grid.csv"), index=False)

    # -------- write report
    write_report(days_sorted, train_days, test_days, missing, allf, corr_df, grid)
    print("[done]", flush=True)

def fmt(x, nd=3):
    if x is None or (isinstance(x, float) and (np.isnan(x))):
        return "  nan"
    return f"{x:.{nd}f}"

def write_report(days_sorted, train_days, test_days, missing, allf, corr_df, grid):
    lines = []
    A = lines.append
    A("# BTC Order-Flow Short-Horizon Predictability — Backtest Report\n")
    A(f"_Generated {pd.Timestamp.utcnow():%Y-%m-%d %H:%M UTC}_\n")
    A("## 1. Sampling achieved\n")
    A(f"- Sampled trading days actually obtained: **{len(days_sorted)}**")
    A(f"- Date span: **{days_sorted[0]} .. {days_sorted[-1]}**")
    A(f"- Bar rows total: {len(allf):,} (1-min bars)")
    A(f"- Missing/skipped dates: {len(missing)}")
    ntr = len(train_days)
    tr_sorted = sorted(train_days); te_sorted = sorted(test_days)
    A(f"- TRAIN = earliest 70% = {len(train_days)} days ({tr_sorted[0]} .. {tr_sorted[-1]})")
    A(f"- TEST  = recent 30%  = {len(test_days)} days ({te_sorted[0]} .. {te_sorted[-1]})\n")

    A("## 2. corr(S_L, ret_H) and momentum sign-hit rate\n")
    A("Positive corr => momentum (flow leads price same way). Negative => reversion (flow fades).\n")
    for split_name in ["TRAIN", "TEST"]:
        A(f"### {split_name}\n")
        A("| L\\H | " + " | ".join(f"H={h}" for h in Hs) + " |")
        A("|---|" + "---|" * len(Hs))
        for L in Ls:
            cells = []
            for H in Hs:
                r = corr_df[(corr_df.split == split_name) & (corr_df.L == L) & (corr_df.H == H)].iloc[0]
                cells.append(f"corr={fmt(r['corr'],4)} hit={fmt(r['signhit_mom'],3)}")
            A(f"| L={L} | " + " | ".join(cells) + " |")
        A("")

    def grid_table(rule, cost):
        A(f"### {rule} rule, round-trip cost = {cost:.0f} bp\n")
        A("Cells: mean_bps/trade | day-clustered t | n_trades  (TRAIN / TEST stacked)\n")
        A("| L\\H | " + " | ".join(f"H={h}" for h in Hs) + " |")
        A("|---|" + "---|" * len(Hs))
        for L in Ls:
            cells = []
            for H in Hs:
                gr = grid[(grid.rule == rule) & (grid.L == L) & (grid.H == H) & (grid.cost == cost)]
                trr = gr[gr.split == "TRAIN"].iloc[0]
                ter = gr[gr.split == "TEST"].iloc[0]
                cells.append(f"TR {fmt(trr['mean_bps'],2)}/t={fmt(trr['t'],2)}/n={int(trr['n'])}<br>"
                             f"TE {fmt(ter['mean_bps'],2)}/t={fmt(ter['t'],2)}/n={int(ter['n'])}")
            A(f"| L={L} | " + " | ".join(cells) + " |")
        A("")

    A("## 3. MOMENTUM rule grid (trade WITH the flow, Z=1.0)\n")
    for cost in COSTS:
        grid_table("MOM", cost)
    A("## 4. REVERSION rule grid (FADE the flow, Z=1.0)\n")
    for cost in COSTS:
        grid_table("REV", cost)

    # ---- verdict logic: same-sign AND significant (|t|>=2) in BOTH train and test, net of cost
    A("## 5. Verdict\n")
    hits = []
    for rule in ["MOM", "REV"]:
        for L in Ls:
            for H in Hs:
                for cost in COSTS:
                    trr = grid[(grid.rule==rule)&(grid.split=="TRAIN")&(grid.L==L)&(grid.H==H)&(grid.cost==cost)].iloc[0]
                    ter = grid[(grid.rule==rule)&(grid.split=="TEST")&(grid.L==L)&(grid.H==H)&(grid.cost==cost)].iloc[0]
                    if (not np.isnan(trr['t']) and not np.isnan(ter['t'])
                        and trr['mean_bps'] > 0 and ter['mean_bps'] > 0
                        and trr['t'] >= 2.0 and ter['t'] >= 2.0):
                        hits.append((rule, L, H, cost, trr['mean_bps'], trr['t'], ter['mean_bps'], ter['t']))
    n_cells = len(grid) // 2  # per (rule,L,H,cost) there are TRAIN+TEST rows
    A(f"Decision rule for 'real': profitable (mean_bps>0) AND day-clustered t>=+2.0 in "
      f"**both** TRAIN and TEST, net of the stated cost. Total (rule,L,H,cost) cells tested = {n_cells}.\n")
    if hits:
        A(f"**POSITIVE: {len(hits)} cell(s) survive in BOTH train and test net of cost:**\n")
        for r, L, H, c, mtr, ttr, mte, tte in hits:
            A(f"- {r} L={L} H={H} cost={c:.0f}bp: TRAIN {mtr:.2f} bps/trade (t={ttr:.2f}), "
              f"TEST {mte:.2f} bps/trade (t={tte:.2f})")
        A("")
    else:
        A("**NULL RESULT.** No (rule, L, H, cost) cell is simultaneously profitable and "
          "statistically significant (day-clustered t>=+2) in BOTH the train and the test split "
          "net of the stated round-trip cost. Order flow does not show robust, out-of-sample, "
          "cost-surviving short-horizon return predictability here — neither the momentum nor the "
          "reversion direction holds up across regimes once trading costs are applied.\n")

    # best test-net cells for transparency
    A("### Strongest TEST-split cells (by |t|), for transparency\n")
    te_grid = grid[grid.split == "TEST"].copy()
    te_grid["abst"] = te_grid["t"].abs()
    top = te_grid.sort_values("abst", ascending=False).head(8)
    A("| rule | L | H | cost | mean_bps | t | n |")
    A("|---|---|---|---|---|---|---|")
    for _, r in top.iterrows():
        A(f"| {r['rule']} | {int(r['L'])} | {int(r['H'])} | {r['cost']:.0f} | "
          f"{fmt(r['mean_bps'],2)} | {fmt(r['t'],2)} | {int(r['n'])} |")
    A("")

    with open("/home/user/Codex-playground-/btc_orderflow_report.md", "w") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
