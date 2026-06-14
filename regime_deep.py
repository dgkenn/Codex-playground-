"""Deep robustness on the survivor regime filters:
 (A) BTC trend (above MA) uptrend gate  -- best OOS18 + drawdown control
 (B) Cross-sectional dispersion gate    -- best REC12, theory-aligned
 (C) combined (trend AND dispersion)
Tests: dense threshold plateau, MA-length robustness, drawdown profile,
year-by-year, and whether the gain is broad (not one window). equal + rank.
"""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
import mom_backtest as mb
import regime_backtest as rb

px, vol = mb.load_panel()
END = px.index.max()

def build(scheme):
    base = rb.base_book(px, vol, mb.sig_riskadj, lb=10, top_n=15, scheme=scheme, cost_bps=9.0)
    return base

def evalg(base, gate):
    g = rb.apply_gate(base, gate, cost_bps=9.0)
    w = rb.windows(g)
    out = {k: mb.stats(rb.slc(g, *w[k]))["sharpe"] for k in ("FULL","IS","OOS18","REC12","PREV12")}
    out["OOSdd"] = rb.maxdd(rb.slc(g, *w["OOS18"]))
    out["RECdd"] = rb.maxdd(rb.slc(g, *w["REC12"]))
    out["FULLdd"] = rb.maxdd(g["net"])
    out["exp"] = g.loc[g.index>=END-pd.DateOffset(months=12),"gate"].abs().mean()
    out["g"] = g
    return out

def yr(g):
    r=g["net"]; o=[]
    for y in (2021,2022,2023,2024,2025,2026):
        ry=r[r.index.year==y]
        o.append(f"{y}:{mb.stats(ry)['sharpe']:+.2f}" if len(ry)>=5 else f"{y}: na")
    return " ".join(o)

for scheme in ("equal","rank"):
    print(f"\n################# SCHEME {scheme} #################")
    base = build(scheme)
    sb = evalg(base, pd.Series(1.0,index=px.index))
    print(f"BASE: FULL {sb['FULL']:+.2f} OOS18 {sb['OOS18']:+.2f} REC12 {sb['REC12']:+.2f} PREV12 {sb['PREV12']:+.2f} "
          f"| FULLdd {sb['FULLdd']*100:+.0f}% OOSdd {sb['OOSdd']*100:+.0f}%")
    print("  yearly:", yr(sb["g"]))

    print("\n-- (A) BTC>MA uptrend gate: DENSE threshold plateau (MA=50) --")
    t50 = rb.btc_trend(px,50)
    print(f"{'thr':>7} | OOS18 REC12 PREV12 | FULLdd OOSdd exp")
    for thr in (-0.12,-0.10,-0.08,-0.06,-0.04,-0.02,0.0,0.02):
        st=evalg(base, rb.gate_from_threshold(t50,thr,"above_on"))
        print(f"{thr:>7.2f} | {st['OOS18']:+.2f} {st['REC12']:+.2f} {st['PREV12']:+.2f} | "
              f"{st['FULLdd']*100:+4.0f}% {st['OOSdd']*100:+4.0f}% {st['exp']:.2f}")
    print("  MA-length robustness at thr=-0.05:")
    for ma in (30,50,75,100,150,200):
        st=evalg(base, rb.gate_from_threshold(rb.btc_trend(px,ma),-0.05,"above_on"))
        print(f"   MA{ma:>3}: OOS18 {st['OOS18']:+.2f} REC12 {st['REC12']:+.2f} PREV12 {st['PREV12']:+.2f} OOSdd {st['OOSdd']*100:+.0f}% exp {st['exp']:.2f}")

    print("\n-- (B) Dispersion gate: DENSE threshold plateau --")
    disp=rb.xs_dispersion(px,lb=10)
    dp=disp.rolling(252,min_periods=60).apply(lambda x:(x.iloc[-1]>=x).mean())
    print(f"{'pctl':>7} | OOS18 REC12 PREV12 | FULLdd OOSdd exp")
    for thr in (0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.40):
        st=evalg(base, rb.gate_from_threshold(dp,thr,"above_on"))
        print(f"{thr:>7.2f} | {st['OOS18']:+.2f} {st['REC12']:+.2f} {st['PREV12']:+.2f} | "
              f"{st['FULLdd']*100:+4.0f}% {st['OOSdd']*100:+4.0f}% {st['exp']:.2f}")

    print("\n-- (C) COMBINED: ON only if (BTC>MA50-0.05) AND (disp pctl>=0.20) --")
    g_trend=rb.gate_from_threshold(t50,-0.05,"above_on")
    g_disp=rb.gate_from_threshold(dp,0.20,"above_on")
    comb=(g_trend*g_disp)
    st=evalg(base, comb)
    print(f"   combined: OOS18 {st['OOS18']:+.2f} REC12 {st['REC12']:+.2f} PREV12 {st['PREV12']:+.2f} "
          f"FULLdd {st['FULLdd']*100:+.0f}% OOSdd {st['OOSdd']*100:+.0f}% exp {st['exp']:.2f}")
    print("   combined yearly:", yr(st["g"]))
    # also OR-blend as half-scale each
    blend=0.5*g_trend+0.5*g_disp
    st2=evalg(base, blend)
    print(f"   soft-blend(0.5/0.5): OOS18 {st2['OOS18']:+.2f} REC12 {st2['REC12']:+.2f} PREV12 {st2['PREV12']:+.2f} OOSdd {st2['OOSdd']*100:+.0f}% exp {st2['exp']:.2f}")
    print("   trend-only(-0.05) yearly:", yr(evalg(base,g_trend)["g"]))
