"""
The honest economics of funding carry: holding-period & breakeven analysis.
Window: 94 days OKX (3 payments/day, 8h funding). Costs explicit below.

Key realism: funding per 8h is TINY (~0.1-0.4 bps). A delta-neutral position needs
4 fills round trip (open 2 legs + close 2 legs). So the question is NOT "harvest every
wobble" (suicidal turnover) but "enter once, hold, collect cumulative funding, exit".
We compute:
  - cumulative gross funding over the window (buy & hold short-perp/long-spot)
  - net after ONE round trip
  - breakeven holding period (how long to hold to cover entry+exit costs)
  - sensitivity to cost level (taker-both vs maker-spot vs maker-both, +slippage)
"""
import numpy as np, pandas as pd
DATA = "/tmp/cx_funding/data"
ASSETS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "LINK", "ADA"]
PY = 3 * 365

# Cost scenarios: round-trip total bps (open 2 legs + close 2 legs)
COSTS = {
    "taker_both+slip (8bps/fill)": 4 * 0.0008,   # 32 bps RT  (pessimistic, market both legs)
    "taker/maker mix (5bps/fill)": 4 * 0.0005,   # 20 bps RT
    "maker_both+slip (3bps/fill)": 4 * 0.0003,   # 12 bps RT  (passive, seconds latency ok)
}

def main():
    print("=== BUY-&-HOLD short-perp/long-spot over full 94d window ===")
    print(f"{'asset':5} {'gross_94d':>10} {'gross_ann':>10} | net_ann under cost scenarios")
    rows=[]
    for a in ASSETS:
        f=pd.read_parquet(f"{DATA}/funding_{a}.parquet").sort_values("fundingTime")
        r=f.fundingRate.values
        n=len(r); days=n/3
        # short-perp collects +funding; if mostly positive, hold short the whole time
        gross=r.sum()                       # cumulative funding over window (short perp)
        gross_ann=gross*PY/n
        line=f"{a:5} {gross*100:9.2f}% {gross_ann*100:9.2f}% |"
        rec=dict(asset=a, gross_94d=gross, gross_ann=gross_ann)
        for label,rt in COSTS.items():
            net=gross-rt
            net_ann=net*PY/n
            # breakeven: periods of avg funding to cover RT cost
            avg=r.mean()
            be_periods=rt/avg if avg>0 else np.inf
            be_days=be_periods/3
            line+=f" {label.split()[0]}:{net_ann*100:6.1f}%(BE {be_days:4.0f}d)"
            rec[label]=net_ann
            rec[label+"_BEdays"]=be_days
        print(line)
        rows.append(rec)
    df=pd.DataFrame(rows)

    print("\n=== BASKET buy&hold (equal-weight), full window ===")
    grs=df.gross_94d.mean(); grs_ann=df.gross_ann.mean()
    print(f"basket gross_ann {grs_ann*100:.2f}%")
    for label,rt in COSTS.items():
        net_ann=(grs-rt)*PY/df.n.iloc[0] if 'n' in df else (grs-rt)*PY/283
        print(f"  net_ann [{label}] = {(grs-rt)*PY/283*100:6.2f}%")

    print("\n=== SENSITIVITY: only-positive-funding assets, single entry, no flips ===")
    # Realistic: pick assets whose funding stayed >0 most of window, hold short the whole time.
    for a in ASSETS:
        f=pd.read_parquet(f"{DATA}/funding_{a}.parquet")
        r=f.fundingRate.values
        pct_pos=(r>0).mean()
        gross_ann=r.sum()*PY/len(r)
        net12=(r.sum()-0.0012)*PY/len(r)  # 12bps RT (maker)
        print(f"{a:5} pct_pos {pct_pos:.0%}  gross_ann {gross_ann*100:6.2f}%  net_ann@12bpsRT {net12*100:6.2f}%")

    df.to_csv("/tmp/cx_funding/data/carry_econ.csv", index=False)

if __name__=="__main__":
    main()
