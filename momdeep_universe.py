"""Follow-up: test XS momentum on the DEPLOYABLE liquid-perp universe only,
and re-derive capacity + the best risk overlay on that universe.

The full 10-coin run is capacity-bound by thin alts (AVAX/LINK/LTC ~$13-16M/day).
A realistic deployment trades only coins with deep perps. Test 6-coin and
8-coin universes, recompute recent-regime Sharpe + capacity.
"""
import numpy as np, pandas as pd, json, warnings
warnings.simplefilter("ignore")
from momdeep_analysis import (load_daily, close_panel, xs_weights, backtest_weights,
                              perf, vol_target_scale, crash_filter_scale,
                              build_funding_panel, ANN, COST_BPS_BASE)

data = load_daily()
px_full = close_panel(data)
last = px_full.index.max()
h18 = last - pd.Timedelta(days=int(18*30.4))
h12 = last - pd.Timedelta(days=365)
fpanel, fstats = build_funding_panel(px_full.index)

UNIS = {
    "10-coin (full)": ["BTC","ETH","SOL","XRP","DOGE","ADA","AVAX","LINK","LTC","BNB"],
    "6-coin (>$30M/d)": ["BTC","ETH","SOL","XRP","DOGE","ADA"],
    "5-coin (>$90M/d)": ["BTC","ETH","SOL","XRP","DOGE"],
    "8-coin (>$15M/d)": ["BTC","ETH","SOL","XRP","DOGE","ADA","BNB","LTC"],
}

print("="*72)
print("UNIVERSE SENSITIVITY: XS 14d/weekly/30%, 7bps, +funding, recent regimes")
print("="*72)
print(f"{'universe':22s} {'full Shp':>8s} {'OOS18 Shp':>9s} {'OOS18 ann':>9s} {'OOS18 dd':>8s} {'OOS12 Shp':>9s}")
rows=[]
for name, u in UNIS.items():
    px = px_full[u].dropna(how="all")
    W = xs_weights(px, 14, 0.30, 7)
    net = backtest_weights(px, W, COST_BPS_BASE, funding_panel=fpanel)["net"]
    pf = perf(net); p18 = perf(net.loc[h18:]); p12 = perf(net.loc[h12:])
    rows.append(dict(universe=name, full=pf["sharpe"], oos18=p18["sharpe"], oos18ann=p18["ann"],
                     oos18dd=p18["maxdd"], oos12=p12["sharpe"]))
    print(f"{name:22s} {pf['sharpe']:8.2f} {p18['sharpe']:9.2f} {p18['ann']*100:8.0f}% {p18['maxdd']*100:7.0f}% {p12['sharpe']:9.2f}")

# Best lookback on the 6-coin deployable universe (recent regime)
print("\n" + "="*72)
print("6-COIN DEPLOYABLE UNIVERSE: lookback x quantile (recent 18mo OOS Sharpe / ann)")
print("="*72)
px6 = px_full[UNIS["6-coin (>$30M/d)"]].dropna(how="all")
grid=[]
for lb in [7,10,14,21,30]:
    line=[]
    for q in [0.20,0.30,0.40]:
        W=xs_weights(px6,lb,q,7)
        net=backtest_weights(px6,W,COST_BPS_BASE,funding_panel=fpanel)["net"]
        p=perf(net.loc[h18:])
        line.append(p["sharpe"]); grid.append(dict(lb=lb,q=q,oos18=p["sharpe"],ann=p["ann"]))
    print(f"  lb={lb:2d}: " + "  ".join(f"q{int(q*100)}={s:+.2f}" for q,s in zip([20,30,40],line)))

# best overlay on 6-coin deployable, recent regime
print("\n" + "="*72)
print("6-COIN: risk overlays on best recent config (recent 18mo OOS)")
print("="*72)
# pick 10d/20% which looked best recently; also show 14d/30%
for lb,q,tag in [(10,0.20,"10d/20%"),(14,0.30,"14d/30%")]:
    px6 = px_full[UNIS["6-coin (>$30M/d)"]].dropna(how="all")
    W=xs_weights(px6,lb,q,7)
    net=backtest_weights(px6,W,COST_BPS_BASE,funding_panel=fpanel)["net"]
    base=perf(net.loc[h18:])
    cf,_,_=crash_filter_scale(px6)
    netc=net*cf
    pc=perf(netc.loc[h18:])
    sc=vol_target_scale(net,0.40)
    netv=net*sc
    pv=perf(netv.loc[h18:])
    netvc=net*sc*cf
    pvc=perf(netvc.loc[h18:])
    print(f"\n{tag}: base Shp {base['sharpe']:.2f} ann {base['ann']*100:.0f}% dd {base['maxdd']*100:.0f}%")
    print(f"   +crashfilter   Shp {pc['sharpe']:.2f} ann {pc['ann']*100:.0f}% dd {pc['maxdd']*100:.0f}%")
    print(f"   +voltgt40      Shp {pv['sharpe']:.2f} ann {pv['ann']*100:.0f}% dd {pv['maxdd']*100:.0f}%")
    print(f"   +voltgt+crash  Shp {pvc['sharpe']:.2f} ann {pvc['ann']*100:.0f}% dd {pvc['maxdd']*100:.0f}%")

# Capacity for 6-coin deployable: thinnest is ADA $31M -> cap
print("\n" + "="*72)
print("6-COIN CAPACITY (thinnest deployable coin = ADA ~$31M/24h)")
print("="*72)
liq = pd.read_parquet("/tmp/cx_momdeep/data_deep/perp_liquidity.parquet")
liq6 = liq[liq.coin.isin(UNIS["6-coin (>$30M/d)"])]
thin = liq6.sort_values("vol24h_usd").iloc[0]
n_legs=2  # 30% of 6 coins ~ 2 per side
print(f"thinnest: {thin['coin']} vol24h=${thin['vol24h_usd']/1e6:.0f}M")
for cap_pct in [0.05,0.10]:
    aum_cap = cap_pct*thin["vol24h_usd"]*n_legs
    print(f"  @{int(cap_pct*100)}% participation/rebalance -> AUM cap ~ ${aum_cap/1e6:.1f}M")

print("\nDONE")
