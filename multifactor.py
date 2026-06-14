"""Cross-sectional MULTI-FACTOR crypto long/short backtest (weekly rebalance).

Sibling agents own the momentum SIGNAL and risk/deploy. THIS agent asks the
single question: does COMBINING lowly-correlated factors beat momentum-alone on
OOS Sharpe AND maxDD, net of realistic perp costs?

Factors (each ranked cross-sectionally each rebalance, dollar-neutral L/S):
  MOM   - 14d trailing return (the anchor; long winners / short losers)
  CARRY - perp funding rate (long LOW/neg funding, short HIGH funding)        [recent window only]
  LOWVOL- 30d realized vol (long LOW vol, short HIGH vol -> the vol anomaly)
  REV   - long-horizon reversal: -(return from t-126d to t-21d) i.e. ~1-2 quarter
          past return, SKIPPING the most recent month (LSV-style, avoids eating MOM)
  SIZE  - liquidity: -(30d avg dollar volume rank) i.e. long SMALLER/less-liquid

Conventions (match sibling momentum engine for comparability):
- Daily OHLCV bars, OKX. Signal on close[t], weights lagged 1 bar (next-bar exec).
- Weekly rebalance: weights recomputed every 7 bars, held between.
- Cost = COST_BPS * turnover (sum |Δweight|) per bar. Base 10 bps round-trip
  (perp taker ~5bps/side OKX + slippage), swept 7/10/12.
- L/S: rank by factor score, long top TOPFRAC, short bottom TOPFRAC, equal-weight
  each leg, scaled so gross leverage = 1 (0.5 long + 0.5 short -> dollar neutral).
- IS = first 65% of dates, OOS = last 35%. Plus a RECENT-regime holdout (last 18mo).
"""
import os, glob, json
import numpy as np
import pandas as pd

DATA = "/tmp/cx_momentum/data"
FUNDING = "/tmp/cx_multifactor/funding_daily.parquet"
ANN = 365.0
IS_FRAC = 0.65
COST_BPS_BASE = 10.0
TOPFRAC = 0.30          # long top 30%, short bottom 30%
RECENT_MONTHS = 18      # hard recent-regime holdout


def load_prices():
    closes, vols = {}, {}
    for fn in glob.glob(f"{DATA}/*_daily.parquet"):
        sym = os.path.basename(fn).split("_")[0].replace("USDT", "")
        df = pd.read_parquet(fn).set_index("ts")
        closes[sym] = df["close"]
        vols[sym] = df["volume_usd"] if "volume_usd" in df else np.nan
    C = pd.concat(closes, axis=1).sort_index()
    V = pd.concat(vols, axis=1).sort_index()
    return C, V


def load_funding(C):
    """Load daily funding and align onto C's index BY CALENDAR DATE (OKX daily bars
    close at 16:00 UTC; dYdX funding is stamped 00:00 UTC -> exact reindex misses)."""
    if not os.path.exists(FUNDING):
        return None
    F = pd.read_parquet(FUNDING)
    F.index = pd.to_datetime(F.index, utc=True).normalize()
    F = F[[c for c in F.columns if c in C.columns]]
    date_to_ts = {ts.normalize(): ts for ts in C.index}
    F = F[F.index.isin(date_to_ts)]
    F.index = F.index.map(date_to_ts)
    return F.reindex(C.index)


def perf(rets):
    rets = rets.dropna()
    if len(rets) < 10 or rets.std() == 0:
        return dict(ann=np.nan, sharpe=np.nan, maxdd=np.nan, n=len(rets))
    eq = (1 + rets).cumprod()
    ann = eq.iloc[-1] ** (ANN / len(rets)) - 1
    sharpe = rets.mean() / rets.std() * np.sqrt(ANN)
    dd = (eq / eq.cummax() - 1).min()
    return dict(ann=float(ann), sharpe=float(sharpe), maxdd=float(dd), n=int(len(rets)))


# ---------- factor SCORES (higher score => more long). all computed at close[t] ----------

def f_mom(C, lb=14):
    return C / C.shift(lb) - 1

def f_lowvol(C, lb=30):
    rv = C.pct_change().rolling(lb).std()
    return -rv                       # long LOW vol

def f_rev(C, skip=21, look=126):
    # past return from t-look to t-skip (skip recent month); reversal => negate
    return -(C.shift(skip) / C.shift(look) - 1)

def f_size(C, V, lb=30):
    adv = V.rolling(lb).mean()
    return -adv                      # long SMALLER ADV (illiquidity premium)

def f_carry(F):
    # F = daily funding rate per asset. long LOW/neg funding, short HIGH => negate
    return -F


def score_to_weights(score, topfrac=TOPFRAC):
    """Cross-sectional dollar-neutral weights from a score matrix (dates x assets)."""
    rank = score.rank(axis=1, pct=True)
    nlong = (rank > 1 - topfrac).astype(float)
    nshort = (rank < topfrac).astype(float)
    lw = nlong.div(nlong.sum(axis=1).replace(0, np.nan), axis=0)
    sw = nshort.div(nshort.sum(axis=1).replace(0, np.nan), axis=0)
    w = (0.5 * lw - 0.5 * sw).fillna(0.0)   # gross leverage ~1, dollar neutral
    return w


def backtest_weights(w_target, rets, reb=7, cost_bps=COST_BPS_BASE):
    """Weekly rebalance: hold target between rebalances; lag 1 bar; net of cost."""
    mask = (np.arange(len(w_target)) % reb == 0)
    held = w_target.where(pd.Series(mask, index=w_target.index), other=np.nan).ffill()
    pos = held.shift(1)
    gross = (pos * rets).sum(axis=1)
    turn = pos.diff().abs().sum(axis=1).fillna(0.0)
    net = gross - turn * (cost_bps / 1e4)
    return net


def zscore(score):
    """Cross-sectional z-score per date (for equal-risk-weight blends)."""
    mu = score.mean(axis=1)
    sd = score.std(axis=1).replace(0, np.nan)
    return score.sub(mu, axis=0).div(sd, axis=0)


def split(idx):
    k = int(len(idx) * IS_FRAC)
    return idx[:k], idx[k:]


def factor_net(name, C, V, F, reb=7, cost_bps=COST_BPS_BASE):
    """Return per-bar net return series for a single factor."""
    if name == "MOM":
        s = f_mom(C)
    elif name == "LOWVOL":
        s = f_lowvol(C)
    elif name == "REV":
        s = f_rev(C)
    elif name == "SIZE":
        s = f_size(C, V)
    elif name == "CARRY":
        s = f_carry(F).reindex(columns=C.columns)
    else:
        raise ValueError(name)
    rets = C.pct_change()
    w = score_to_weights(s)
    net = backtest_weights(w, rets, reb, cost_bps)
    if name == "CARRY":
        # mask to the funding-data window (no carry signal before funding exists)
        fund_dates = s.dropna(how="all").index
        if len(fund_dates):
            net = net.where(net.index >= fund_dates.min())
    return net, s


def main():
    C, V = load_prices()
    rets = C.pct_change()
    F = load_funding(C)

    out = {}

    # ---- 1. standalone factor OOS ----
    price_factors = ["MOM", "LOWVOL", "REV", "SIZE"]
    nets = {}
    for name in price_factors:
        net, _ = factor_net(name, C, V, F)
        nets[name] = net
    # carry only over the funding window
    if F is not None and F.shape[1] >= 4:
        net_c, _ = factor_net("CARRY", C, V, F)
        nets["CARRY"] = net_c.dropna()

    standalone = []
    for name, net in nets.items():
        idx = net.dropna().index
        is_idx, oos_idx = split(idx)
        standalone.append(dict(factor=name,
            full_sharpe=perf(net)["sharpe"],
            is_sharpe=perf(net.loc[is_idx])["sharpe"],
            oos_sharpe=perf(net.loc[oos_idx])["sharpe"],
            oos_ann=perf(net.loc[oos_idx])["ann"],
            oos_maxdd=perf(net.loc[oos_idx])["maxdd"],
            n=len(idx), start=str(idx.min().date()), end=str(idx.max().date())))
    out["standalone"] = standalone

    # ---- 1b. cross-correlations of factor net returns (full overlap) ----
    netdf = pd.DataFrame({k: v for k, v in nets.items()})
    corr = netdf.corr()
    out["corr"] = corr.round(3).to_dict()

    # also OOS-window correlation (price factors, common OOS)
    common = netdf[price_factors].dropna()
    _, oos_idx = split(common.index)
    out["corr_oos"] = netdf.loc[oos_idx, price_factors].corr().round(3).to_dict()

    json.dump(out, open("/tmp/cx_multifactor/standalone.json", "w"), indent=2, default=str)

    print("\n===== STANDALONE FACTORS (10bps, weekly) =====")
    print(pd.DataFrame(standalone).to_string(index=False))
    print("\n===== FACTOR NET-RETURN CORRELATION (full overlap) =====")
    print(corr.round(2).to_string())
    print("\n===== CORRELATION over PRICE-FACTOR OOS window =====")
    print(netdf.loc[oos_idx, price_factors].corr().round(2).to_string())

    # save net series for the combination script
    netdf.to_parquet("/tmp/cx_multifactor/factor_nets.parquet")
    print("\nsaved factor_nets.parquet", netdf.shape)


if __name__ == "__main__":
    main()
