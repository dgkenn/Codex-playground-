#!/usr/bin/env python3
"""Run the small-bankroll execution-realism study; prints all tables."""
import numpy as np
import pandas as pd
import etf_smallbankroll as sb

pd.set_option("display.width", 200, "display.max_columns", 60)

adj = sb.load(sb.ADJ)
raw = sb.load(sb.RAW)
UNIV = sb.CORE_UNIVERSE
FULL = "2000-06-01"
RECENT = "2016-01-01"


def line(t):
    print("\n" + "=" * 92 + "\n" + t + "\n" + "=" * 92)


def fmt(eq, diag=None, label=""):
    s = sb.equity_stats(eq)
    d = dict(config=label, CAGR=round(s["CAGR"], 4), Sharpe=round(s["Sharpe"], 3),
             maxDD=round(s["maxDD"], 3), vol=round(s["vol"], 3))
    if diag:
        d["cashDrag"] = round(diag["avg_cash_drag"], 3)
        d["distort"] = round(diag["avg_distortion"], 3)
    return d


# ---------------------------------------------------------------------------
# DELIVERABLE 1: WHOLE-SHARE / CASH-DRAG by bankroll
# ---------------------------------------------------------------------------
def deliv1(start, tag):
    line(f"1. WHOLE-SHARE drag by bankroll vs FRACTIONAL ideal  [{tag}]  K=5, DUAL+regime 6m, p=0.34")
    # fractional ideal is bankroll-invariant; compute once
    eqf, df = sb.simulate_dollar(adj, raw, UNIV, 100000, mode="fractional", start=start)
    sf = sb.equity_stats(eqf)
    print(f"  FRACTIONAL IDEAL: CAGR {sf['CAGR']*100:5.2f}%  Sharpe {sf['Sharpe']:.3f}  "
          f"maxDD {sf['maxDD']*100:5.1f}%  cashDrag {df['avg_cash_drag']:.3f}  "
          f"distort {df['avg_distortion']:.3f}")
    rows = []
    for cap in [500, 1000, 5000, 10000, 100000]:
        eq, dg = sb.simulate_dollar(adj, raw, UNIV, cap, mode="whole", start=start)
        s = sb.equity_stats(eq)
        rows.append(dict(bankroll=f"${cap:,}",
                         CAGR=round(s["CAGR"], 4), Sharpe=round(s["Sharpe"], 3),
                         maxDD=round(s["maxDD"], 3),
                         dCAGR_pp=round((s["CAGR"] - sf["CAGR"]) * 100, 2),
                         dSharpe=round(s["Sharpe"] - sf["Sharpe"], 3),
                         cashDrag=round(dg["avg_cash_drag"], 3),
                         distort=round(dg["avg_distortion"], 3)))
    print(pd.DataFrame(rows).to_string(index=False))
    return sf


# ---------------------------------------------------------------------------
# DELIVERABLE 2: MITIGATIONS at $1k (and $500)
# ---------------------------------------------------------------------------
def deliv2(start, tag):
    line(f"2. MITIGATIONS at small bankroll  [{tag}]")
    for cap in [1000, 500]:
        print(f"\n  --- bankroll ${cap:,} ---")
        rows = []
        # (baseline) whole-share K=5
        eq, dg = sb.simulate_dollar(adj, raw, UNIV, cap, mode="whole", start=start)
        rows.append(fmt(eq, dg, "whole K=5 (baseline)"))
        # (a) fractional
        eq, dg = sb.simulate_dollar(adj, raw, UNIV, cap, mode="fractional", start=start)
        rows.append(fmt(eq, dg, "FRACTIONAL K=5"))
        # (b) fewer positions: top-3
        eq, dg = sb.simulate_dollar(adj, raw, UNIV, cap, mode="whole", K=3, start=start)
        rows.append(fmt(eq, dg, "whole K=3"))
        eq, dg = sb.simulate_dollar(adj, raw, UNIV, cap, mode="whole", K=4, start=start)
        rows.append(fmt(eq, dg, "whole K=4"))
        # (c) cheaper-ETF universe
        cu = cheap_universe()
        eq, dg = sb.simulate_dollar(adj, raw, cu, cap, mode="whole", start=start)
        rows.append(fmt(eq, dg, "whole K=5 CHEAP-univ"))
        # (d) greedy hold-what-fits
        eq, dg = sb.simulate_dollar(adj, raw, UNIV, cap, mode="greedy", start=start)
        rows.append(fmt(eq, dg, "GREEDY K=5"))
        # combo: greedy + K=3
        eq, dg = sb.simulate_dollar(adj, raw, UNIV, cap, mode="greedy", K=3, start=start)
        rows.append(fmt(eq, dg, "GREEDY K=3"))
        # combo: greedy + cheap univ
        eq, dg = sb.simulate_dollar(adj, raw, cu, cap, mode="greedy", start=start)
        rows.append(fmt(eq, dg, "GREEDY K=5 CHEAP-univ"))
        print(pd.DataFrame(rows).to_string(index=False))


def cheap_universe():
    """Apply CHEAP_SUBS to the core universe; keep only tickers present in data."""
    out = []
    for t in UNIV:
        sub = sb.CHEAP_SUBS.get(t, t)
        if sub in adj.columns and raw[sub].notna().sum() > 250:
            out.append(sub)
        elif t in adj.columns:
            out.append(t)
    return sorted(set(out))


# ---------------------------------------------------------------------------
# DELIVERABLE 3: REBALANCE-TIMING LUCK
# ---------------------------------------------------------------------------
def deliv3(start, tag):
    line(f"3. REBALANCE-TIMING luck (day 1/8/15/22 + month-end + 4-way tranche)  [{tag}]  FRACTIONAL K=5")
    rows = []
    curves = {}
    for day in [1, 8, 15, 22, None]:
        eq, dg = sb.simulate_dollar(adj, raw, UNIV, 100000, mode="fractional",
                                    start=start, rebal_day=day)
        curves[day] = eq
        rows.append(fmt(eq, None, f"rebal day {'EOM' if day is None else day}"))
    # 4-way tranche: average daily return of the 4 day-of-month variants
    rets = []
    common = None
    for day in [1, 8, 15, 22]:
        r = curves[day].pct_change()
        common = r.index if common is None else common.intersection(r.index)
        rets.append(r)
    rets = [r.reindex(common) for r in rets]
    tranche_ret = sum(rets) / 4.0
    tranche_eq = (1 + tranche_ret.fillna(0)).cumprod() * 100000
    rows.append(fmt(tranche_eq, None, "4-WAY TRANCHE (avg)"))
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    sub = df[df.config.str.startswith("rebal")]
    print(f"\n  Dispersion across 5 rebalance days: CAGR {sub.CAGR.min()*100:.2f}-{sub.CAGR.max()*100:.2f}% "
          f"(spread {(sub.CAGR.max()-sub.CAGR.min())*100:.2f}pp), "
          f"Sharpe {sub.Sharpe.min():.3f}-{sub.Sharpe.max():.3f} (spread {sub.Sharpe.max()-sub.Sharpe.min():.3f})")


# ---------------------------------------------------------------------------
# DELIVERABLE 4: INDEPENDENT UNIVERSE CONFIRMATION
# ---------------------------------------------------------------------------
def deliv4(start, tag):
    line(f"4. INDEPENDENT universe confirmation (not re-optimization)  [{tag}]  FRACTIONAL K=5")
    rows = []
    eq, _ = sb.simulate_dollar(adj, raw, UNIV, 100000, mode="fractional", start=start)
    rows.append(fmt(eq, None, f"full {len(UNIV)}-name core"))
    # drop 3 highest-priced (by latest raw price)
    last = raw[UNIV].ffill().iloc[-1].sort_values(ascending=False)
    drop3 = last.head(3).index.tolist()
    u2 = [t for t in UNIV if t not in drop3]
    eq, _ = sb.simulate_dollar(adj, raw, u2, 100000, mode="fractional", start=start)
    rows.append(fmt(eq, None, f"drop 3 priciest ({','.join(drop3)})"))
    # fixed 20-name subset: sectors + style core + key macro (deterministic, no opt)
    fixed20 = sorted(set(sb.SECTORS + ["SPY", "QQQ", "IWM"] +
                         ["EFA", "EEM", "TLT", "GLD", "VNQ", "HYG", "DBC"]))[:20]
    eq, _ = sb.simulate_dollar(adj, raw, fixed20, 100000, mode="fractional", start=start)
    rows.append(fmt(eq, None, f"fixed {len(fixed20)}-name subset"))
    # cheaper-universe (also a different name list)
    cu = cheap_universe()
    eq, _ = sb.simulate_dollar(adj, raw, cu, 100000, mode="fractional", start=start)
    rows.append(fmt(eq, None, f"cheap-substituted {len(cu)}-name"))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    for start, tag in [(FULL, "FULL 2000-2026"), (RECENT, "RECENT 2016-2026")]:
        deliv1(start, tag)
    for start, tag in [(FULL, "FULL"), (RECENT, "RECENT")]:
        deliv2(start, tag)
    for start, tag in [(FULL, "FULL"), (RECENT, "RECENT")]:
        deliv3(start, tag)
    for start, tag in [(FULL, "FULL"), (RECENT, "RECENT")]:
        deliv4(start, tag)
    print("\n[done]")
