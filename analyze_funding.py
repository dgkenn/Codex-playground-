"""
Analyze OKX perp funding-carry as a delta-neutral harvest strategy.
Data window: ~94 days (OKX public funding-rate-history hard-caps ~3 months).
Funding interval: 8h (3 payments/day) on OKX USDT perps for these majors.

REALISM LENS: cloud bot, seconds latency, modest capital, 1-2 venues.
Strategy: delta-neutral. funding>0 => SHORT perp + LONG spot (collect funding from longs).
funding<0 => LONG perp + SHORT spot (or skip if can't short spot). We collect |funding|
in the direction that pays us, IF we are positioned. Always-on neutral carry collects
sign(funding)*funding only if we flip sides each period; realistically a perp-only +
spot setup harvests POSITIVE funding (short perp / long spot) cleanly. We model both:
  (A) directional-perfect: collect |funding| every period (requires shorting spot for neg)
  (B) long-spot-only: collect funding only when funding>0 (short perp+long spot), else flat.

Costs: round-trip taker/maker fees on BOTH legs + basis slippage. We do NOT trade every
period; we hold and only pay costs on entry/exit and on flips/rebalances.
"""
import json, os
import numpy as np
import pandas as pd

DATA = "/tmp/cx_funding/data"
ASSETS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "LINK", "ADA"]
PERIODS_PER_YEAR = 3 * 365  # 8h funding => 1095 periods/yr

# Cost assumptions (per LEG, one side). OKX taker ~0.05% spot, ~0.05% perp (no/low VIP).
# A delta-neutral position = open both legs (2 legs) + close both legs (2 legs) = 4 taker fills.
FEE_TAKER = 0.0005      # 5 bps per fill
FEE_MAKER = 0.0002      # 2 bps per fill (achievable with seconds latency, passive)
SLIP_BPS = 0.0003       # 3 bps basis/slippage cushion per fill
# Realistic blended: assume taker on perp, maker-ish on spot; use a per-fill cost.
PER_FILL = (FEE_TAKER + SLIP_BPS)  # 8 bps/fill conservative; 4 fills round trip = 32 bps


def load():
    out = {}
    for a in ASSETS:
        f = pd.read_parquet(f"{DATA}/funding_{a}.parquet").sort_values("fundingTime").reset_index(drop=True)
        out[a] = f
    return out


def characterize(fund):
    rows = []
    for a, f in fund.items():
        r = f.fundingRate.values
        ann = r.mean() * PERIODS_PER_YEAR
        med_ann = np.median(r) * PERIODS_PER_YEAR
        std_ann = r.std() * np.sqrt(PERIODS_PER_YEAR)
        pos = (r > 0).mean()
        # autocorrelation lag1
        ac1 = np.corrcoef(r[:-1], r[1:])[0, 1] if len(r) > 2 else np.nan
        # persistence: P(next same sign | this sign)
        s = np.sign(r)
        same = (s[:-1] == s[1:]).mean()
        rows.append(dict(asset=a, n=len(r), mean_ann=ann, median_ann=med_ann,
                         std_ann=std_ann, pct_pos=pos, ac1=ac1, persist_sign=same,
                         mean_8h_bps=r.mean()*1e4, std_8h_bps=r.std()*1e4))
    return pd.DataFrame(rows)


def backtest_asset(f, mode="A", thresh=0.0, fee_per_fill=PER_FILL, exit_band=None):
    """Return (pnl series, num_transitions). pnl = per-period net return on notional.
    mode A: harvest |funding| (short-perp if funding>+enter, long-perp if <-enter).
    mode B: long-spot/short-perp only; harvest funding when funding>enter.
    HYSTERESIS: enter when |funding|>thresh; once in, HOLD (no cost) until funding
    crosses an exit band (exit_band, default = thresh/2) on the wrong side. This avoids
    churning the 2-leg book on every tiny sign wobble. Costs = 2 fills to open + 2 to close."""
    r = f.fundingRate.values
    n = len(r)
    pnl = np.zeros(n)
    pos = 0
    trans = 0
    enter = thresh
    exitb = thresh / 2 if exit_band is None else exit_band
    leg = 2 * fee_per_fill  # one side (open or close) = 2 legs = 2 fills
    for t in range(n):
        ft = r[t]
        # decide target with hysteresis
        if mode == "A":
            if pos == 0:
                want = -1 if ft > enter else (1 if ft < -enter else 0)
            elif pos == -1:
                want = -1 if ft > -exitb else (1 if ft < -enter else 0)  # stay short while not deeply neg
            else:  # pos == 1
                want = 1 if ft < exitb else (-1 if ft > enter else 0)
        else:  # B
            if pos == 0:
                want = -1 if ft > enter else 0
            else:  # pos == -1
                want = -1 if ft > exitb else 0
        if want != pos:
            if pos != 0:
                pnl[t] -= leg; trans += 1
            if want != 0:
                pnl[t] -= leg; trans += 1
        if want == -1:
            pnl[t] += ft
        elif want == 1:
            pnl[t] += -ft
        pos = want
    return pnl, trans


def stats(pnl):
    pnl = np.asarray(pnl)
    n = len(pnl)
    tot = pnl.sum()
    ann = pnl.mean() * PERIODS_PER_YEAR
    vol = pnl.std() * np.sqrt(PERIODS_PER_YEAR)
    sharpe = ann / vol if vol > 0 else np.nan
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak)
    maxdd = dd.min()
    return dict(ann_ret=ann, ann_vol=vol, sharpe=sharpe, total_ret=tot,
                maxdd=maxdd, hit=(pnl > 0).mean())


def main():
    fund = load()
    days = (fund["BTC"].fundingTime.max() - fund["BTC"].fundingTime.min()) / 1000 / 86400
    print(f"=== DATA WINDOW: {days:.0f} days, {len(fund['BTC'])} periods/asset (8h) ===\n")

    char = characterize(fund)
    print("=== FUNDING CHARACTERIZATION (annualized) ===")
    print(char.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # Net carry backtests
    out_rows = []
    for a, f in fund.items():
        for mode in ["A", "B"]:
            for thr in [0.0, 0.0001, 0.0002, 0.0005]:  # 0, 1, 2, 5 bps per 8h threshold
                pnl, tr = backtest_asset(f, mode=mode, thresh=thr)
                st = stats(pnl)
                out_rows.append(dict(asset=a, mode=mode, thr_bps=thr*1e4, trans=tr,
                                     trans_per_yr=tr/len(pnl)*PERIODS_PER_YEAR, **st))
    bt = pd.DataFrame(out_rows)

    print("\n=== NET CARRY AFTER COSTS (per asset), cost = %.0f bps/fill (2 fills/side) ==="
          % (PER_FILL*1e4))
    show = bt[(bt.thr_bps.isin([0.0, 2.0]))]
    print(show.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Gross (no cost) comparison
    print("\n=== GROSS vs NET (mode A, thr=0 vs thr=2bps w/ hysteresis) ===")
    for a, f in fund.items():
        g, _ = backtest_asset(f, "A", 0.0, fee_per_fill=0.0)
        nt0, tr0 = backtest_asset(f, "A", 0.0, fee_per_fill=PER_FILL)
        nt2, tr2 = backtest_asset(f, "A", 0.0002, fee_per_fill=PER_FILL)
        print(f"{a}: gross {stats(g)['ann_ret']*100:6.2f}%  net@thr0 {stats(nt0)['ann_ret']*100:7.2f}%"
              f" ({tr0} trans)  net@thr2 {stats(nt2)['ann_ret']*100:6.2f}% ({tr2} trans)")

    # BASKET: equal-weight across assets
    print("\n=== BASKET (equal-weight all assets) ===")
    for mode in ["A", "B"]:
        for thr in [0.0, 0.0002, 0.0005]:
            mats = np.array([backtest_asset(f, mode, thr)[0] for f in fund.values()])
            basket = mats.mean(axis=0)
            st = stats(basket)
            print(f"mode {mode} thr {thr*1e4:.0f}bps: ann {st['ann_ret']*100:6.2f}%  "
                  f"vol {st['ann_vol']*100:5.2f}%  Sharpe {st['sharpe']:5.2f}  maxDD {st['maxdd']*100:6.2f}%")

    # CROSS-SECTIONAL: each period, harvest top-K highest |funding| assets (mode A)
    print("\n=== CROSS-SECTIONAL: harvest top-K highest-|funding| assets each period (mode A) ===")
    fr = np.array([f.fundingRate.values for f in fund.values()])  # assets x time
    nT = fr.shape[1]
    for K in [1, 2, 3]:
        port = np.zeros(nT)
        prev_sel = set()
        for t in range(nT):
            absf = np.abs(fr[:, t])
            sel = np.argsort(absf)[::-1][:K]
            per = 0.0
            for i in sel:
                ft = fr[i, t]
                carry = abs(ft)  # mode A collects |funding|
                # cost: pay round-trip if newly entered (rough: treat each period entry conservatively)
                cost = 0.0
                if i not in prev_sel:
                    cost = 2 * PER_FILL  # entry only this turn (4 fills/2 amortized—conservative)
                per += (carry - cost)
            port[t] = per / K
            prev_sel = set(sel.tolist())
        st = stats(port)
        print(f"K={K}: ann {st['ann_ret']*100:6.2f}%  vol {st['ann_vol']*100:5.2f}%  "
              f"Sharpe {st['sharpe']:5.2f}  maxDD {st['maxdd']*100:6.2f}%")

    # Save machine-readable
    char.to_csv("/tmp/cx_funding/data/char.csv", index=False)
    bt.to_csv("/tmp/cx_funding/data/backtest.csv", index=False)
    print("\nsaved char.csv, backtest.csv")


if __name__ == "__main__":
    main()
