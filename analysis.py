"""Crypto mean-reversion / stat-arb research.
Realism lens: cloud bot, seconds-to-minutes latency (slow taker), modest capital.
All backtests are SLOW TAKER: signal computed on bar CLOSE, fill at NEXT bar OPEN,
both legs cross the spread. Cost = taker fee + slippage per side. No look-ahead.

Sources: OKX public spot USDT candles. Binance/Bybit geo-blocked (not used).
"""
import os, glob, json, itertools
import numpy as np, pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller, coint
import statsmodels.api as sm

DATA = "/tmp/cx_statarb/data"
RES = {}

# ---- realistic round-trip cost assumptions (per leg, fraction) ----
# OKX taker spot fee ~ 8-10 bps; slippage for modest size at minute horizon ~ 2-5 bps.
TAKER_FEE = 0.0008      # 8 bps per side
SLIPPAGE  = 0.0004      # 4 bps per side
COST_PER_SIDE = TAKER_FEE + SLIPPAGE   # 12 bps per side, one-way on notional traded

BARS_PER_YEAR = {"1H": 24*365, "15m": 4*24*365, "1D": 365}

def load(sym, bar):
    fn = f"{DATA}/{sym}_{bar}.parquet"
    if not os.path.exists(fn): return None
    df = pd.read_parquet(fn).set_index("ts")
    return df

def load_panel(bar, cols="c"):
    syms = sorted({os.path.basename(f).rsplit("_",1)[0] for f in glob.glob(f"{DATA}/*_{bar}.parquet")})
    out = {}
    for s in syms:
        d = load(s, bar)
        if d is None or len(d) < 200: continue
        out[s] = d[cols]
    px = pd.DataFrame(out).dropna(how="all")
    return px

def perf_stats(ret, bar, ann=None):
    """ret = per-bar net return series (strategy)."""
    ret = ret.dropna()
    if len(ret) < 10 or ret.std()==0:
        return dict(n=len(ret), ann_ret=np.nan, sharpe=np.nan, maxdd=np.nan, hit=np.nan, trades=np.nan)
    bpy = ann or BARS_PER_YEAR[bar]
    mean, sd = ret.mean(), ret.std()
    sharpe = mean/sd*np.sqrt(bpy)
    eq = (1+ret).cumprod()
    ann_ret = eq.iloc[-1]**(bpy/len(ret)) - 1
    dd = (eq/eq.cummax()-1).min()
    hit = (ret>0).mean()
    return dict(n=int(len(ret)), ann_ret=float(ann_ret), sharpe=float(sharpe),
                maxdd=float(dd), hit=float(hit))

# ===================================================================
# 2. PAIRS / COINTEGRATION STAT-ARB
# ===================================================================
def hedge_ratio_ols(y, x):
    X = sm.add_constant(x)
    b = sm.OLS(y, X).fit().params
    return b.iloc[1], b.iloc[0]  # beta, intercept

def zscore(s, win):
    m = s.rolling(win).mean(); sd = s.rolling(win).std()
    return (s-m)/sd

def backtest_pair(py, px, bar, win_hedge=500, win_z=200, z_in=2.0, z_out=0.5, cost=COST_PER_SIDE):
    """Rolling-hedge spread; z-score reversion; slow taker, next-bar fill, both legs costed.
    Returns per-bar net return on gross notional ~ 2x (long+short). Cost applied on position change of each leg."""
    df = pd.DataFrame({"y":py,"x":px}).dropna()
    ly, lx = np.log(df.y), np.log(df.x)
    # rolling hedge ratio (causal)
    beta = pd.Series(index=df.index, dtype=float)
    # use expanding-capped rolling regression via covariance for speed
    cov = lx.rolling(win_hedge).cov(ly)
    var = lx.rolling(win_hedge).var()
    beta = (cov/var)
    spread = ly - beta*lx
    z = zscore(spread, win_z)
    # position on spread: -1 when z>z_in (short spread), +1 when z<-z_in; exit when |z|<z_out
    pos = pd.Series(0.0, index=df.index)
    cur = 0.0
    zv = z.values
    pv = np.zeros(len(zv))
    for i in range(len(zv)):
        if np.isnan(zv[i]):
            pv[i]=0.0; cur=0.0; continue
        if cur==0:
            if zv[i]>z_in: cur=-1.0
            elif zv[i]<-z_in: cur=1.0
        else:
            if abs(zv[i])<z_out: cur=0.0
            elif cur==1.0 and zv[i]>z_in: cur=-1.0  # flip
            elif cur==-1.0 and zv[i]<-z_in: cur=1.0
        pv[i]=cur
    pos = pd.Series(pv, index=df.index)
    # spread return per bar: pos held over bar -> realized next bar. shift signal by 1 (decide on close, hold next bar)
    # spread pnl = pos * d(spread) but spread uses log prices; approximate dollar-neutral legs:
    ry = ly.diff(); rx = lx.diff()
    # holding spread long = long y, short beta*x
    spread_ret = pos.shift(1) * (ry - beta.shift(1)*rx)
    # transaction cost: when pos changes, both legs trade. gross notional per leg ~ (1 + |beta|)
    leg_notional = (1 + beta.abs()).shift(1).fillna(1.0)
    turns = pos.diff().abs().fillna(0.0)  # 0->1 =1, flip 1->-1 =2
    tc = turns * leg_notional * cost
    net = spread_ret - tc
    n_trades = int((pos.diff().abs()>0).sum())
    return net, pos, z, beta, n_trades

# ===================================================================
# 3. TIME-SERIES MEAN-REVERSION (single asset, 1-6h)
# ===================================================================
def backtest_ts_reversion(close, bar, lookback=24, z_in=2.0, z_out=0.5, hold_cap=12, cost=COST_PER_SIDE):
    """Reversion on single asset log-price z-score vs rolling mean. Slow taker, next-bar fill.
    Fade overextension: z>z_in -> short, z<-z_in -> long, exit |z|<z_out."""
    lp = np.log(close).dropna()
    z = zscore(lp, lookback)
    pos = pd.Series(0.0, index=lp.index)
    cur=0.0; held=0
    zv=z.values; pv=np.zeros(len(zv))
    for i in range(len(zv)):
        if np.isnan(zv[i]): pv[i]=0.0; cur=0.0; held=0; continue
        if cur!=0: held+=1
        if cur==0:
            if zv[i]>z_in: cur=-1.0; held=0
            elif zv[i]<-z_in: cur=1.0; held=0
        else:
            if abs(zv[i])<z_out or held>=hold_cap: cur=0.0; held=0
        pv[i]=cur
    pos=pd.Series(pv,index=lp.index)
    r = lp.diff()
    gross = pos.shift(1)*r
    turns = pos.diff().abs().fillna(0.0)
    tc = turns*cost
    net = gross - tc
    n_trades=int((pos.diff().abs()>0).sum())
    return net, n_trades

# ===================================================================
# 4. RESIDUAL / CROSS-SECTIONAL REVERSION (alt on BTC)
# ===================================================================
def backtest_residual(alt_close, btc_close, bar, win_hedge=500, win_z=120, z_in=2.0, z_out=0.5, cost=COST_PER_SIDE):
    """Regress log(alt) on log(BTC) rolling; trade residual reversion. Market-neutral (short BTC hedge)."""
    df = pd.DataFrame({"a":alt_close,"b":btc_close}).dropna()
    la, lb = np.log(df.a), np.log(df.b)
    cov = lb.rolling(win_hedge).cov(la); var=lb.rolling(win_hedge).var()
    beta = cov/var
    resid = la - beta*lb
    z = zscore(resid, win_z)
    cur=0.0; zv=z.values; pv=np.zeros(len(zv))
    for i in range(len(zv)):
        if np.isnan(zv[i]): pv[i]=0.0; cur=0.0; continue
        if cur==0:
            if zv[i]>z_in: cur=-1.0
            elif zv[i]<-z_in: cur=1.0
        else:
            if abs(zv[i])<z_out: cur=0.0
        pv[i]=cur
    pos=pd.Series(pv,index=df.index)
    ra, rb = la.diff(), lb.diff()
    gross = pos.shift(1)*(ra - beta.shift(1)*rb)
    leg = (1+beta.abs()).shift(1).fillna(1.0)
    turns = pos.diff().abs().fillna(0.0)
    tc = turns*leg*cost
    net = gross - tc
    n_trades=int((pos.diff().abs()>0).sum())
    return net, n_trades

# ===================================================================
# 5. LATENCY HONESTY: autocorrelation of returns at multiple horizons
# ===================================================================
def latency_decay(close, bar, max_lag=24):
    """Lag-1 autocorr of bar returns at increasing aggregation. Negative => reversion.
    If reversion only at smallest bar (5-15m) and vanishes by 1H, it's near/at our latency floor."""
    out={}
    lp = np.log(close).dropna()
    for agg in [1,2,3,6,12,24]:
        # non-overlapping aggregated log returns
        sampled = lp.iloc[::agg]
        ra = sampled.diff().dropna()
        if len(ra)<50: continue
        ac1 = ra.autocorr(lag=1)
        out[agg]=ac1
    return out

def is_oos_split(idx, frac=0.6):
    n=len(idx); k=int(n*frac)
    return idx[:k], idx[k:]
