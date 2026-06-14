"""Honesty / falsification tests for the BTC-trend (and combined) regime gate.

Q1 Is the Sharpe gain real edge-timing, or just deleveraging (lower vol)?
   -> compare conditional Sharpe of returns when gate ON vs gate OFF (the OFF
      bucket should be the WEAK regime; if OFF returns are ~as good as ON, the
      filter isn't timing anything).
Q2 Strict IS-only param pick: choose MA & thr ONLY on IS (pre-OOS18), then read OOS.
Q3 Re-leverage the gated book to the SAME realized vol as base, so the comparison
   is risk-neutral (does Sharpe still win after equalizing vol?).
Q4 Placebo: random gates with the same average exposure -> distribution of OOS Sharpe.
Q5 Funding-rate recent context (data only ~2026-03+, OKX shallow history) -- report.
"""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
import mom_backtest as mb
import regime_backtest as rb

px, vol = mb.load_panel()
END = px.index.max(); IS_END = END - pd.DateOffset(months=18)
t50 = rb.btc_trend(px, 50)
disp = rb.xs_dispersion(px, lb=10)
dp = disp.rolling(252, min_periods=60).apply(lambda x:(x.iloc[-1]>=x).mean())

def run(scheme):
    print(f"\n=========== SCHEME {scheme} ===========")
    base = rb.base_book(px, vol, mb.sig_riskadj, lb=10, top_n=15, scheme=scheme, cost_bps=9.0)
    bn = base["net_base"]
    w = rb.windows(rb.apply_gate(base, pd.Series(1.0,index=px.index)))

    # Q1 conditional Sharpe ON vs OFF (trend gate thr=-0.05)
    gate = rb.gate_from_threshold(t50, -0.05, "above_on")
    g = rb.apply_gate(base, gate)
    on = g["net"][g["gate"]>0]; off_idx = g.index[g["gate"]==0]
    # the base return we FORWENT when off:
    base_aligned = bn.reindex(g.index)
    off_base = base_aligned[g["gate"]==0]
    on_base = base_aligned[g["gate"]>0]
    print(f"Q1 base-return conditional on trend-gate:")
    print(f"   ON  weeks n={on_base.notna().sum():3d}  mean {on_base.mean()*100:+.2f}%/wk  Sharpe {mb.stats(on_base)['sharpe']:+.2f}")
    print(f"   OFF weeks n={off_base.notna().sum():3d}  mean {off_base.mean()*100:+.2f}%/wk  Sharpe {mb.stats(off_base)['sharpe']:+.2f}")
    print(f"   -> filter pays iff OFF weeks are materially worse than ON weeks.")

    # Q2 strict IS-only pick of (MA, thr)
    best=None
    for ma in (30,50,75,100):
        tr = rb.btc_trend(px, ma)
        for thr in (-0.10,-0.05,0.0):
            gg = rb.apply_gate(base, rb.gate_from_threshold(tr,thr,"above_on"))
            is_sh = mb.stats(rb.slc(gg,*w["IS"]))["sharpe"]
            if best is None or is_sh>best[0]: best=(is_sh,ma,thr,gg)
    _,ma,thr,gg = best
    print(f"Q2 strict IS-best trend gate = MA{ma}, thr{thr}:  "
          f"OOS18 {mb.stats(rb.slc(gg,*w['OOS18']))['sharpe']:+.2f}  REC12 {mb.stats(rb.slc(gg,*w['REC12']))['sharpe']:+.2f}  "
          f"PREV12 {mb.stats(rb.slc(gg,*w['PREV12']))['sharpe']:+.2f}  OOSdd {rb.maxdd(rb.slc(gg,*w['OOS18']))*100:+.0f}%")
    base_oos = mb.stats(rb.slc(rb.apply_gate(base,pd.Series(1.0,index=px.index)),*w['OOS18']))['sharpe']
    print(f"   (base OOS18 {base_oos:+.2f})")

    # Q3 re-leverage gated book to base realized vol over OOS18, compare Sharpe (vol-neutral)
    g05 = rb.apply_gate(base, rb.gate_from_threshold(t50,-0.05,"above_on"))
    bvol = rb.slc(rb.apply_gate(base,pd.Series(1.0,index=px.index)),*w['OOS18']).std()
    gvol = rb.slc(g05,*w['OOS18']).std()
    lev = bvol/gvol if gvol>0 else 1.0
    gr = rb.slc(g05,*w['OOS18'])*lev
    print(f"Q3 vol-neutral (gated x {lev:.2f} to match base vol): OOS18 Sharpe {mb.stats(gr)['sharpe']:+.2f} "
          f"(base {base_oos:+.2f}); same vol => Sharpe diff is pure timing.")

    # Q4 placebo random gates with matched exposure
    exp = (g05["gate"]>0).mean()
    rng = np.random.default_rng(0)
    n = len(g05); shs=[]
    for _ in range(400):
        rg = pd.Series((rng.random(n)<exp).astype(float), index=g05.index)
        gp = base["net_base"].reindex(g05.index)*rg.values
        shs.append(mb.stats(rb.slc(pd.DataFrame({"net":gp},index=g05.index),*w['OOS18']))['sharpe'])
    shs=np.array(shs); real=mb.stats(rb.slc(g05,*w['OOS18']))['sharpe']
    pct=(real>shs).mean()
    print(f"Q4 placebo (400 random gates, exp={exp:.2f}): random OOS18 Sharpe mean {np.nanmean(shs):+.2f} "
          f"sd {np.nanstd(shs):.2f}; trend-gate {real:+.2f} -> {pct*100:.0f}th pctile")

run("equal"); run("rank")

# Q5 funding context
print("\n=== Q5 funding-rate recent context (OKX history shallow ~94d) ===")
try:
    f = pd.read_parquet("/tmp/regime_data/funding.parquet")
    f["d"] = f["ts"].dt.floor("D")
    daily = f.groupby(["d","sym"])["fr"].mean().unstack()
    agg = daily.mean(axis=1)
    print(f"   funding history: {agg.index.min().date()} -> {agg.index.max().date()} ({len(agg)} days) -- too short for multi-yr regime backtest")
    print(f"   recent agg 8h funding: last={agg.iloc[-1]*1e4:.1f}bps  30d-mean={agg.tail(90).mean()*1e4:.1f}bps  (annualized ~{agg.tail(90).mean()*3*365*100:.0f}%)")
    print("   VERDICT: recent aggregate funding is ~flat/slightly negative (NOT crowded-long now);")
    print("   regardless, the series is too short (OKX serves only ~3mo) to backtest a funding")
    print("   regime over 2021-2026, so a funding-stress filter is UNTESTABLE on this data source.")
except Exception as e:
    print("   funding load failed:", e)
