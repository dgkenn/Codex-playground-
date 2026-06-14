"""Cross-sectional crypto momentum DE-RISKING engine.

Tasks:
 1. Parameter robustness sweep (lookback x rebalance x quantile) -> Sharpe surface;
    recent 12-18mo OOS holdout -> realistic forward expectation.
 2. Short-side funding interaction (OKX funding netted into P&L).
 3. Crash/tail risk: vol-targeting + crash filter overlays.
 4. Execution + capacity: slippage, per-coin capacity, net at $10k/$100k/$1M.
 5. Deployable spec inputs.

Data:
  Daily OHLCV: /tmp/cx_momentum/data/<COIN>USDT_daily.parquet (OKX, 2019-11 -> 2026-06)
  Funding:     /tmp/cx_momdeep/data_deep/<COIN>_funding.parquet (OKX, ~last 3mo)
  Perp liq:    /tmp/cx_momdeep/data_deep/perp_liquidity.parquet
"""
import os, glob, json, warnings
import numpy as np
import pandas as pd
warnings.simplefilter("ignore")

DATA = "/tmp/cx_momentum/data"
DEEP = "/tmp/cx_momdeep/data_deep"
ANN = 365.0
COST_BPS_BASE = 7.0          # round-trip taker+slippage on modest size, per |dpos|
UNIVERSE = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC", "BNB"]


# ---------------- data ----------------
def load_daily():
    out = {}
    for sym in UNIVERSE:
        fn = f"{DATA}/{sym}USDT_daily.parquet"
        if os.path.exists(fn):
            df = pd.read_parquet(fn).set_index("ts").sort_index()
            out[sym] = df
    return out


def close_panel(data):
    px = pd.DataFrame({s: d["close"] for s, d in data.items()}).sort_index()
    return px


def perf(r, ann=ANN):
    r = pd.Series(r).dropna()
    if len(r) < 10 or r.std() == 0:
        return dict(ann=np.nan, sharpe=np.nan, maxdd=np.nan, n=len(r))
    eq = (1 + r).cumprod()
    return dict(ann=float(eq.iloc[-1] ** (ann / len(r)) - 1),
                sharpe=float(r.mean() / r.std() * np.sqrt(ann)),
                maxdd=float((eq / eq.cummax() - 1).min()), n=int(len(r)))


# ---------------- XS momentum core ----------------
def xs_weights(px, lookback, quantile, rebalance_days):
    """Cross-sectional momentum target weights (dollar-neutral, equal-weight legs).
    Long top-`quantile`, short bottom-`quantile`. Weights rebalanced every
    `rebalance_days`; held (carried) between rebalances on a fixed-weight basis.
    Returns daily target-weight panel (already decision-time; lag applied later).
    """
    ret = px.pct_change(lookback)
    dates = px.index
    W = pd.DataFrame(0.0, index=dates, columns=px.columns)
    last_w = pd.Series(0.0, index=px.columns)
    for i, dt in enumerate(dates):
        if i % rebalance_days == 0:
            r = ret.loc[dt].dropna()
            n = len(r)
            if n >= 4:
                k = max(1, int(np.floor(n * quantile)))
                order = r.sort_values()
                shorts = order.index[:k]
                longs = order.index[-k:]
                w = pd.Series(0.0, index=px.columns)
                w[longs] = 1.0 / len(longs)
                w[shorts] = -1.0 / len(shorts)
                last_w = w
        W.loc[dt] = last_w
    return W


def backtest_weights(px, W, cost_bps=COST_BPS_BASE, funding_panel=None):
    """Returns daily net strategy return given target weights W.
    Position lagged 1 day (decide on close[t], hold over t->t+1).
    cost charged on |dweight| (turnover). funding_panel: daily funding accrual
    rate per coin (fraction/day) where POSITIVE means longs pay shorts.
    Strategy funding pnl = -W_lagged * funding (short leg with positive funding earns)."""
    Wl = W.shift(1).fillna(0.0)
    rr = px.pct_change()
    gross = (Wl * rr).sum(axis=1)
    turn = (Wl.diff().abs().sum(axis=1)).fillna(0.0)
    cost = turn * (cost_bps / 1e4)
    net = gross - cost
    fund = pd.Series(0.0, index=px.index)
    if funding_panel is not None:
        fp = funding_panel.reindex(px.index).reindex(columns=px.columns)
        # funding rate positive => longs pay, shorts receive.
        # position pnl from funding = -position * funding_rate
        fund = -(Wl * fp).sum(axis=1)
        net = net + fund
    return dict(net=net, gross=gross, cost=cost, fund=fund, turn=turn)


# ---------------- vol targeting + crash filter ----------------
def vol_target_scale(net_daily, target_ann=0.40, win=30, cap=2.0, floor=0.1):
    rv = net_daily.rolling(win).std() * np.sqrt(ANN)
    scale = (target_ann / rv).clip(upper=cap, lower=floor)
    return scale.shift(1).fillna(1.0)  # lag: size off yesterday's realized vol


def market_drawdown(px, eq_weight=True):
    """Equal-weight market index drawdown (proxy for crypto beta regime)."""
    idx = (1 + px.pct_change()).cumprod().mean(axis=1)
    dd = idx / idx.cummax() - 1
    return idx, dd


def crash_filter_scale(px, dd_thresh=-0.20, vol_win=20, vol_thresh_q=0.90):
    """Stand-down / de-gross signal:
       gross down to 0.5x when equal-weight market in deep drawdown (< dd_thresh)
       OR market realized vol above its rolling 90th pct."""
    idx, dd = market_drawdown(px)
    mret = idx.pct_change()
    rvol = mret.rolling(vol_win).std() * np.sqrt(ANN)
    vthr = rvol.rolling(180, min_periods=60).quantile(vol_thresh_q)
    deep = dd < dd_thresh
    spikevol = rvol > vthr
    scale = pd.Series(1.0, index=px.index)
    scale[deep | spikevol] = 0.5
    return scale.shift(1).fillna(1.0), dd, rvol


# ---------------- funding panel from OKX ----------------
def build_funding_panel(px_index):
    """Daily funding rate per coin (fraction/day). OKX funding is per 8h (3/day).
    Positive => longs pay shorts. Only ~last 3 months available from public API."""
    daily = {}
    for sym in UNIVERSE:
        fn = f"{DEEP}/{sym}_funding.parquet"
        if not os.path.exists(fn):
            continue
        f = pd.read_parquet(fn).set_index("fundingTime").sort_index()
        # sum the (up to 3) intraday funding events into a daily rate
        d = f["fundingRate"].resample("1D").sum()
        d.index = d.index.tz_convert("UTC") if d.index.tz else d.index
        daily[sym] = d
    if not daily:
        return None, {}
    panel = pd.DataFrame(daily)
    panel.index = panel.index.normalize()
    # reindex to px daily index (px stamped 16:00 UTC); align by date
    px_dates = pd.DatetimeIndex(px_index).normalize()
    panel = panel.reindex(px_dates).set_axis(px_index)
    stats = {s: float(panel[s].dropna().mean()) for s in panel.columns}
    return panel, stats


# ============================================================
def main():
    data = load_daily()
    px = close_panel(data)
    print("Universe:", list(px.columns), " window:", px.index.min().date(), "->", px.index.max().date(), "n=", len(px))

    # Define recent OOS holdout = last 18 months (hard forward proxy)
    last = px.index.max()
    holdout_start = last - pd.Timedelta(days=int(18 * 30.4))
    holdout12_start = last - pd.Timedelta(days=365)
    print("18mo holdout:", holdout_start.date(), "-> 12mo holdout:", holdout12_start.date())

    results = {}

    # ---------- TASK 1: ROBUSTNESS SURFACE ----------
    print("\n" + "=" * 70)
    print("TASK 1: PARAMETER ROBUSTNESS SURFACE (net of 7bps cost, NO funding)")
    print("=" * 70)
    lookbacks = [7, 10, 14, 21, 30]
    rebals = {"weekly": 7, "biweekly": 14}
    quants = [0.20, 0.30, 0.40]
    surface = []
    for lb in lookbacks:
        for rname, rd in rebals.items():
            for q in quants:
                W = xs_weights(px, lb, q, rd)
                bt = backtest_weights(px, W)
                full = perf(bt["net"])
                # splits
                oos18 = perf(bt["net"].loc[holdout_start:])
                oos12 = perf(bt["net"].loc[holdout12_start:])
                surface.append(dict(lookback=lb, rebalance=rname, quantile=q,
                                    full_sharpe=full["sharpe"], full_ann=full["ann"],
                                    oos18_sharpe=oos18["sharpe"], oos18_ann=oos18["ann"], oos18_dd=oos18["maxdd"],
                                    oos12_sharpe=oos12["sharpe"], oos12_ann=oos12["ann"]))
    surf = pd.DataFrame(surface)
    results["surface"] = surf.to_dict("records")
    # print weekly surface
    print("\n--- FULL-HISTORY Sharpe surface (weekly rebalance) ---")
    piv = surf[surf.rebalance == "weekly"].pivot(index="lookback", columns="quantile", values="full_sharpe")
    print(piv.round(2).to_string())
    print("\n--- RECENT 18mo OOS Sharpe surface (weekly rebalance) ---")
    piv2 = surf[surf.rebalance == "weekly"].pivot(index="lookback", columns="quantile", values="oos18_sharpe")
    print(piv2.round(2).to_string())
    print("\n--- RECENT 18mo OOS Sharpe surface (biweekly rebalance) ---")
    piv3 = surf[surf.rebalance == "biweekly"].pivot(index="lookback", columns="quantile", values="oos18_sharpe")
    print(piv3.round(2).to_string())
    print("\n--- RECENT 18mo OOS ann return surface (weekly) ---")
    piv4 = surf[surf.rebalance == "weekly"].pivot(index="lookback", columns="quantile", values="oos18_ann")
    print((piv4*100).round(0).to_string())

    # plateau vs spike diagnostic
    wk = surf[surf.rebalance == "weekly"]
    print(f"\nFULL surface (weekly): Sharpe mean={wk.full_sharpe.mean():.2f} sd={wk.full_sharpe.std():.2f} "
          f"min={wk.full_sharpe.min():.2f} max={wk.full_sharpe.max():.2f}")
    print(f"OOS18 surface (weekly): Sharpe mean={wk.oos18_sharpe.mean():.2f} sd={wk.oos18_sharpe.std():.2f} "
          f"min={wk.oos18_sharpe.min():.2f} max={wk.oos18_sharpe.max():.2f}")
    frac_pos = (wk.oos18_sharpe > 0).mean()
    print(f"OOS18 fraction of weekly configs with Sharpe>0: {frac_pos*100:.0f}%")

    # baseline config used downstream
    base_lb, base_q, base_rd = 14, 0.30, 7
    W = xs_weights(px, base_lb, base_q, base_rd)
    bt = backtest_weights(px, W)
    print(f"\nBASELINE 14d/weekly/30%: full Sharpe {perf(bt['net'])['sharpe']:.2f} ann {perf(bt['net'])['ann']*100:.0f}% | "
          f"OOS18 Sharpe {perf(bt['net'].loc[holdout_start:])['sharpe']:.2f} ann {perf(bt['net'].loc[holdout_start:])['ann']*100:.0f}% "
          f"dd {perf(bt['net'].loc[holdout_start:])['maxdd']*100:.0f}%")

    # regime folds (3 equal thirds) to show decay
    print("\n--- DECAY: baseline 14d/weekly/30% across 4 equal time folds ---")
    idx = bt["net"].dropna().index
    folds = np.array_split(idx, 4)
    fold_rows = []
    for j, fdx in enumerate(folds):
        p = perf(bt["net"].loc[fdx])
        fold_rows.append(dict(fold=j+1, start=str(fdx[0].date()), end=str(fdx[-1].date()),
                              sharpe=round(p["sharpe"],2), ann=round(p["ann"]*100,0), dd=round(p["maxdd"]*100,0)))
        print(f"  fold{j+1} {fdx[0].date()}->{fdx[-1].date()}: Sharpe {p['sharpe']:.2f} ann {p['ann']*100:.0f}% dd {p['maxdd']*100:.0f}%")
    results["folds"] = fold_rows
    results["baseline_oos18"] = perf(bt["net"].loc[holdout_start:])
    results["baseline_oos12"] = perf(bt["net"].loc[holdout12_start:])

    # ---------- TASK 2: SHORT-SIDE FUNDING ----------
    print("\n" + "=" * 70)
    print("TASK 2: SHORT-SIDE FUNDING INTERACTION (OKX, last ~3mo actual)")
    print("=" * 70)
    fpanel, fstats = build_funding_panel(px.index)
    liq = pd.read_parquet(f"{DEEP}/perp_liquidity.parquet")
    print("\nMean funding rate per coin (%/8h) and annualized (positive => shorts RECEIVE):")
    for s in UNIVERSE:
        if s in fstats:
            per8h = fstats[s] / 3.0  # daily back to per-8h avg
            print(f"  {s:5s} {per8h*100:+.4f}%/8h  ann={fstats[s]*365*100:+.1f}%/yr")
    results["funding_stats_daily"] = fstats

    # Net funding into baseline over the funding window
    if fpanel is not None:
        fwin = fpanel.dropna(how="all").index
        fwin = fwin[fwin >= fpanel.dropna(how="all").index.min()]
        bt_nf = backtest_weights(px, W)  # no funding
        bt_wf = backtest_weights(px, W, funding_panel=fpanel)  # with funding
        # restrict to funding-available window
        fstart = fpanel.dropna(how="all").index.min()
        sub_nf = bt_nf["net"].loc[fstart:]
        sub_wf = bt_wf["net"].loc[fstart:]
        sub_fund = bt_wf["fund"].loc[fstart:]
        p_nf = perf(sub_nf); p_wf = perf(sub_wf)
        print(f"\nOver funding window {fstart.date()}->{px.index.max().date()} ({len(sub_nf)}d):")
        print(f"  Strategy ann WITHOUT funding: {p_nf['ann']*100:+.0f}%  Sharpe {p_nf['sharpe']:.2f}")
        print(f"  Strategy ann WITH    funding: {p_wf['ann']*100:+.0f}%  Sharpe {p_wf['sharpe']:.2f}")
        ann_fund = sub_fund.mean() * 365
        print(f"  Net funding contribution: {ann_fund*100:+.2f}%/yr  (mean {sub_fund.mean()*1e4:+.2f} bps/day)")
        results["funding_window"] = dict(start=str(fstart.date()),
                                         ann_no_fund=p_nf["ann"], ann_with_fund=p_wf["ann"],
                                         net_funding_ann=float(ann_fund))

    # Shortability table
    print("\nShortability / liquidity (OKX USDT-perp):")
    liq_sorted = liq.sort_values("vol24h_usd", ascending=False)
    for _, row in liq_sorted.iterrows():
        oi = (row.get("oi_usd") or 0)/1e6
        v = (row.get("vol24h_usd") or 0)/1e6
        print(f"  {row['coin']:5s} OI=${oi:7.1f}M  vol24h=${v:7.0f}M  perp={'YES' if row['inst'] else 'no'}")
    results["liquidity"] = liq_sorted.to_dict("records")

    # ---------- TASK 3: CRASH / TAIL RISK + OVERLAYS ----------
    print("\n" + "=" * 70)
    print("TASK 3: CRASH / TAIL RISK + RISK OVERLAYS (baseline 14d/weekly/30%)")
    print("=" * 70)
    base_net = bt_nf["net"] if 'bt_nf' in dir() else backtest_weights(px, W)["net"]
    base_net = backtest_weights(px, W)["net"]
    # worst drawdowns
    eq = (1 + base_net.dropna()).cumprod()
    dd = eq / eq.cummax() - 1
    print(f"\nBaseline maxDD full history: {dd.min()*100:.0f}% on {dd.idxmin().date()}")
    # worst 10 daily returns + their dates vs market dd
    idx_mkt, mkt_dd = market_drawdown(px)
    worst = base_net.dropna().sort_values().head(8)
    print("Worst 8 daily strategy returns (momentum-crash days) and market drawdown that day:")
    for d, v in worst.items():
        print(f"  {d.date()}: strat {v*100:+.1f}%  | market dd {mkt_dd.loc[d]*100:.0f}%")

    overlays = {}
    p_base = perf(base_net)
    overlays["base"] = p_base
    # vol target
    for tgt in [0.30, 0.40, 0.50]:
        sc = vol_target_scale(base_net, target_ann=tgt)
        nv = base_net * sc
        overlays[f"voltgt_{int(tgt*100)}"] = perf(nv)
    # crash filter
    cf, _, _ = crash_filter_scale(px)
    nc = base_net * cf
    overlays["crashfilter"] = perf(nc)
    # combo: vol target 40 + crash filter
    sc = vol_target_scale(base_net, 0.40)
    cf2, _, _ = crash_filter_scale(px)
    ncombo = base_net * sc * cf2
    overlays["voltgt40+crash"] = perf(ncombo)

    print("\nOverlay comparison (full history):")
    print(f"  {'overlay':18s} {'Sharpe':>7s} {'ann%':>7s} {'maxDD%':>7s}")
    for k, p in overlays.items():
        print(f"  {k:18s} {p['sharpe']:7.2f} {p['ann']*100:7.0f} {p['maxdd']*100:7.0f}")
    # also on OOS18
    print("\nOverlay comparison (recent 18mo OOS):")
    ov18 = {}
    for k, ser in [("base", base_net),
                   ("voltgt40", base_net*vol_target_scale(base_net,0.40)),
                   ("crashfilter", base_net*crash_filter_scale(px)[0]),
                   ("voltgt40+crash", base_net*vol_target_scale(base_net,0.40)*crash_filter_scale(px)[0])]:
        p = perf(ser.loc[holdout_start:])
        ov18[k] = p
        print(f"  {k:18s} {p['sharpe']:7.2f} {p['ann']*100:7.0f} {p['maxdd']*100:7.0f}")
    results["overlays_full"] = {k: v for k, v in overlays.items()}
    results["overlays_oos18"] = ov18

    # ---------- TASK 4: EXECUTION + CAPACITY ----------
    print("\n" + "=" * 70)
    print("TASK 4: EXECUTION + CAPACITY (net Sharpe/return after frictions)")
    print("=" * 70)
    # turnover of baseline
    Wl = W.shift(1).fillna(0.0)
    gross_turn_per_rebal = Wl.diff().abs().sum(axis=1)
    weekly_turn = gross_turn_per_rebal[gross_turn_per_rebal > 0]
    ann_turnover = gross_turn_per_rebal.sum() / (len(px)/365.0)
    print(f"Avg gross turnover per rebalance: {weekly_turn.mean():.2f} (sum |dweight|)")
    print(f"Annualized gross turnover: {ann_turnover:.1f}x notional/yr")

    # capacity: per rebalance, each coin gets ~ (1/n_legs) of gross notional.
    # cap participation at ~10% of 24h perp $volume per coin per rebalance.
    n_legs = 3  # ~30% of 10 coins each side
    print("\nNotional traded per coin per weekly rebalance vs 24h perp volume:")
    print("(rule of thumb: keep per-rebalance trade <= 10% of coin 24h $vol for ~single-digit-bps slippage)")
    cap_rows = []
    for _, row in liq.iterrows():
        v = row.get("vol24h_usd") or 0
        cap_per_coin = 0.10 * v  # max trade per rebalance
        # weight per coin per leg ~ 1/n_legs; turnover ~ full leg twice on full rotation
        # AUM cap such that (AUM * weight_per_coin) <= cap_per_coin; weight ~ 1/n_legs
        aum_cap = cap_per_coin * n_legs
        cap_rows.append(dict(coin=row["coin"], vol24h_usd=v, aum_cap_usd=aum_cap))
    capdf = pd.DataFrame(cap_rows).sort_values("aum_cap_usd")
    binding = capdf.iloc[0]
    print(capdf.assign(vol24h_M=lambda d: (d.vol24h_usd/1e6).round(0),
                       aum_cap_M=lambda d: (d.aum_cap_usd/1e6).round(1))[["coin","vol24h_M","aum_cap_M"]].to_string(index=False))
    print(f"\nBinding (thinnest) coin: {binding['coin']} -> portfolio AUM cap ~= ${binding['aum_cap_usd']/1e6:.1f}M "
          f"for <=10% participation/rebalance")
    results["capacity"] = capdf.to_dict("records")

    # slippage-adjusted net at scale: model slippage as fn of participation
    # base 7bps already includes modest slippage. Add incremental slippage by scale.
    print("\nNet performance (recent 18mo OOS regime) at different AUM, with scale-dependent cost:")
    oos_net_base = base_net  # we recompute per cost
    aum_levels = [1e4, 1e5, 1e6, 1e7]
    # crude slippage model: extra_bps = k * (per_coin_trade / (0.10*vol)) ; here use thinnest coin
    thin_vol = capdf.iloc[0]["vol24h_usd"]
    scale_rows = []
    for aum in aum_levels:
        per_coin_trade = aum / n_legs
        partic = per_coin_trade / max(thin_vol, 1)  # fraction of 24h vol on thinnest coin
        # slippage: ~ taker(8bps each way=16 rt) base already; add convex impact
        extra = 30.0 * (partic / 0.10)  # 30bps when at the 10% cap, linear-ish below
        cost_bps = COST_BPS_BASE + max(0.0, extra)
        W2 = xs_weights(px, base_lb, base_q, base_rd)
        net2 = backtest_weights(px, W2, cost_bps=cost_bps, funding_panel=fpanel if fpanel is not None else None)["net"]
        # apply recommended overlay (voltgt40 + crash)
        net2o = net2 * vol_target_scale(net2,0.40) * crash_filter_scale(px)[0]
        p = perf(net2o.loc[holdout_start:])
        scale_rows.append(dict(aum=aum, cost_bps=round(cost_bps,1), partic_thin=round(partic*100,2),
                               oos18_sharpe=round(p["sharpe"],2), oos18_ann=round(p["ann"]*100,0), oos18_dd=round(p["maxdd"]*100,0)))
        print(f"  AUM ${aum:>11,.0f}: cost {cost_bps:5.1f}bps  thin-coin partic {partic*100:5.2f}%  "
              f"OOS18 Sharpe {p['sharpe']:.2f}  ann {p['ann']*100:.0f}%  dd {p['maxdd']*100:.0f}%")
    results["scale_net"] = scale_rows

    # Deployable universe (only liquid perps): drop coins with vol24h < $30M as non-deployable at scale
    deployable = [r["coin"] for r in liq.to_dict("records") if (r.get("vol24h_usd") or 0) >= 30e6]
    print(f"\nLiquid-perp deployable universe (vol24h>=$30M): {deployable}")
    results["deployable_universe"] = deployable

    # final recommended config net (recent regime, with funding + overlay, modest scale)
    print("\n" + "=" * 70)
    print("RECOMMENDED CONFIG NET (recent 18mo OOS, 14d/weekly/30%, voltgt40+crash, +funding, $100k):")
    W_rec = xs_weights(px, 14, 0.30, 7)
    net_rec = backtest_weights(px, W_rec, cost_bps=COST_BPS_BASE, funding_panel=fpanel)["net"]
    net_rec_o = net_rec * vol_target_scale(net_rec,0.40) * crash_filter_scale(px)[0]
    p_rec18 = perf(net_rec_o.loc[holdout_start:])
    p_rec12 = perf(net_rec_o.loc[holdout12_start:])
    print(f"  OOS18: Sharpe {p_rec18['sharpe']:.2f}  ann {p_rec18['ann']*100:.0f}%  maxDD {p_rec18['maxdd']*100:.0f}%")
    print(f"  OOS12: Sharpe {p_rec12['sharpe']:.2f}  ann {p_rec12['ann']*100:.0f}%  maxDD {p_rec12['maxdd']*100:.0f}%")
    results["recommended_oos18"] = p_rec18
    results["recommended_oos12"] = p_rec12

    with open("/tmp/cx_momdeep/momdeep_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nWrote momdeep_results.json")


if __name__ == "__main__":
    main()
