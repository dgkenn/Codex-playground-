"""kalshi_sizing.py -- smart, FEE-AWARE bet sizing for the Kalshi 15m maker, backtested on the REAL
trade tape (trades_kalshi_*.parquet + hist_kalshi_*.parquet).

WHY SIZING IS THE FEE LEVER. Kalshi's fee (where charged) is fee = mult * p * (1-p) per contract --
QUADRATIC in price, maximal at p=0.5, ~0 at the tails. So the optimal clip is not flat: it should
shrink where the fee eats the capture (mid prices) and grow where the net edge is real (benign,
fee-cheap fills). The unifying rule:

    size(fill) ∝ max(0, edge_hat) ,  edge_hat = E[markout | features] - fee(p)

with E[markout|features] from the decision-time toxicity signal (the same micro/spot-gate the bot
already runs), then fractional-Kelly scaled and hard-capped by inventory + notional. With fee=0 this
is pure benign-volume sizing; with fee>0 it auto-tightens around p=0.5 -- the fee-conditional edge.

SIZING RULES COMPARED (each held to settlement on the real tape, queue-replayed at q_ahead):
  flat        : 1 unit every fill (the current bot)
  gate        : 1 unit if the spot-gate says benign, else 0
  level       : taper by |p-0.5| (more size at fee-cheap tails) -- pure fee-shape response
  edge_kelly  : size ∝ max(0, mhat - fee(p)), clipped to [0, KMAX] -- the unified rule
all under fee ∈ {0 (BTC confirmed), 0.0175*p(1-p) (other-series worst case)}, IS/OOS split,
scored by net/win, per-fill net, Sharpe(t), and Calmar (risk-adjusted -- the standing discipline).

    python kalshi_sizing.py btc
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

GATE_BPS = 8.0           # |3-min spot move| bps: the decision-time toxicity flag (>this = adverse side)
KMAX = 3.0               # max Kelly-scaled clip (units); hard inventory/notional cap on top
KELLY_FRAC = 0.5         # fractional Kelly (half) -- standard prudent scaling


def fee_of(p, mult):
    return mult * p * (1.0 - p)


def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 8 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def calmar(net_by_win):
    cum = np.cumsum(net_by_win)
    mdd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0
    tot = float(cum[-1]) if len(cum) else 0.0
    return (tot / mdd) if mdd > 1e-9 else (float("inf") if tot > 0 else 0.0)


def collect_fills(hist, tap, q0=0.0):
    """Replay the real tape -> one record per FILL with its decision-time features + realized markout
    and settlement. Features are honest (spot move BEFORE the fill, candle-shifted one bar stale)."""
    common = sorted(set(hist.index) & set(tap.index))
    recs = []
    for w in common:
        h = hist.loc[w]; t = tap.loc[w]
        res = float(h.res_up)
        bid = np.asarray(h.bid_path, float); ask = np.asarray(h.ask_path, float)
        mid = np.asarray(h.mid_path, float)
        spot = np.asarray(h.spot_path, float)
        spot_l = np.concatenate([[np.nan], spot[:-1]])      # candle close k known at minute k+1
        t_arr = np.asarray(t.t, float); p_arr = np.asarray(t.p, float)
        sz_arr = np.asarray(t.sz, float); buy_arr = np.asarray(t.buy, bool)
        for k in range(2, 13):
            b0, a0, m0 = bid[k], ask[k], mid[k]
            if np.isnan(b0) or np.isnan(a0) or not (0.03 <= m0 <= 0.97):
                continue
            s_now, s_then = spot_l[k], spot_l[max(k - 3, 0)]
            mv = (s_now / s_then - 1) * 1e4 if (s_now > 0 and s_then > 0) else 0.0
            m_next = mid[k + 1] if (k + 1 < 15 and not np.isnan(mid[k + 1])) else m0
            spread = a0 - b0
            tau = (15 - k) / 15.0                                  # fraction of window remaining
            # prior-minute signed taker flow imbalance (decision-time toxicity: who's hitting?)
            pl, ph = w + 60 * (k - 1), w + 60 * k
            pj0, pj1 = np.searchsorted(t_arr, pl), np.searchsorted(t_arr, ph)
            flow = float(np.sum(np.where(buy_arr[pj0:pj1], sz_arr[pj0:pj1], -sz_arr[pj0:pj1]))) / 1000.0
            lo, hi = w + 60 * (k + 1), w + 60 * (k + 2)
            i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
            qb = qa = q0; done_b = done_a = False
            for i in range(i0, i1):
                if done_b and done_a:
                    break
                p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
                if not done_b and not buy and p <= b0 + 1e-9:        # BID fill (bought yes@b0); flow>0 (buyers) adverse to a bid
                    if qb >= sz:
                        qb -= sz
                    else:
                        recs.append((w, "bid", b0, res - b0, (m_next - b0), mv, spread, tau, flow))
                        done_b = True
                if not done_a and buy and p >= a0 - 1e-9:            # ASK fill (sold yes@a0); flow<0 adverse to an ask
                    if qa >= sz:
                        qa -= sz
                    else:
                        recs.append((w, "ask", a0, a0 - res, (a0 - m_next), -mv, spread, tau, -flow))
                        done_a = True
    return pd.DataFrame(recs, columns=["ws", "side", "p", "settle", "markout", "sig_adv", "spread", "tau", "flow_adv"])


def size_rule(name, df, mult, mhat):
    """Return per-fill size (units) under a rule. mhat = predicted markout (the toxicity model)."""
    p = df.p.to_numpy(); adv = df.sig_adv.to_numpy()
    if name == "flat":
        return np.ones(len(df))
    if name == "gate":                                  # 1 if benign side, else 0
        return (adv <= GATE_BPS).astype(float)
    if name == "level":                                 # taper toward fee-cheap tails
        return np.clip(1.0 + 2.0 * (np.abs(p - 0.5) - 0.25), 0.0, KMAX)
    if name == "edge_kelly":                            # the unified fee-aware rule
        edge = mhat - fee_of(p, mult)                   # predicted net per contract
        # fractional Kelly on a ~unit-variance per-fill bet -> size ∝ edge; clip, zero if negative
        return np.clip(KELLY_FRAC * edge / 0.02, 0.0, KMAX)
    return np.ones(len(df))


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else "btc"
    q0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    hist = pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws")
    tap = pd.read_parquet(f"trades_kalshi_{asset}15m.parquet").set_index("ws")
    df = collect_fills(hist, tap, q0)
    n = len(df)
    print(f"{asset}: {n} real fills across {df.ws.nunique()} windows | q_ahead={q0:g} (front=0)\n")

    # predicted markout mhat: fit on IS only (first 60% of windows) -- linear on [1, sig_adv, |p-.5|],
    # target = realized 1-min markout. Honest OOS: predict on the test half with IS coefficients.
    wins = np.sort(df.ws.unique()); cut = wins[int(len(wins) * 0.6)]
    is_m = (df.ws < cut).to_numpy(); oos_m = ~is_m
    feat_cols = ["sig_adv", "spread", "tau", "flow_adv"]
    X = np.column_stack([np.ones(n), df.sig_adv.to_numpy(), np.abs(df.p.to_numpy()-0.5),
                         df.spread.to_numpy(), df.tau.to_numpy(), df.flow_adv.to_numpy()])
    y = df.markout.to_numpy()
    coef, *_ = np.linalg.lstsq(X[is_m], y[is_m], rcond=None)
    mhat = X @ coef
    # OOS R^2 of the markout model (is the predictor real?)
    ss_res = np.sum((y[oos_m]-mhat[oos_m])**2); ss_tot=np.sum((y[oos_m]-y[is_m].mean())**2)
    print(f"markout model (IS fit, OOS R^2={1-ss_res/ss_tot:+.4f}):")
    print(f"  bias{coef[0]:+.4f} sig_adv{coef[1]:+.5f} |p-.5|{coef[2]:+.4f} "
          f"spread{coef[3]:+.4f} tau{coef[4]:+.4f} flow_adv{coef[5]:+.4f}\n")

    for mult in (0.0, 0.0175):
        tag = "FEE=0 (BTC confirmed live)" if mult == 0 else "FEE=0.0175*p(1-p) (other-series worst case)"
        print(f"=== {tag} ===")
        print(f"{'rule':>11} {'units/win':>9} {'net/win(c)':>11} {'perfill(c)':>11} "
              f"{'Sharpe':>7} {'OOS net':>8} {'OOS Cal':>8}")
        for rule in ("flat", "gate", "level", "edge_kelly"):
            sz = size_rule(rule, df, mult, mhat)
            # per-fill net = size * (settlement - fee), fee charged per contract
            net = sz * (df.settle.to_numpy() - fee_of(df.p.to_numpy(), mult))
            by_win = pd.Series(net).groupby(df.ws.to_numpy()).sum()
            ow = np.array([w for w in by_win.index])
            oos_win = by_win.to_numpy()[ow >= cut]
            units = sz.sum() / df.ws.nunique()
            print(f"{rule:>11} {units:>9.2f} {by_win.mean()*100:>+11.2f} "
                  f"{(net[sz>0].mean()*100 if (sz>0).any() else 0):>+11.3f} "
                  f"{tstat(by_win.to_numpy()):>+7.1f} {oos_win.mean()*100:>+8.2f} "
                  f"{calmar(oos_win):>8.1f}")
        print()
    print("Read: net/win in CENTS per window (sizing-weighted). edge_kelly should win on Calmar/OOS")
    print("ESPECIALLY when fee>0 -- it shrinks size where p*(1-p) fee bites and grows it on benign")
    print("fee-cheap fills. With fee=0 it converges toward benign-volume sizing. q_ahead set via argv[2] (0 = front, where sub-cent improve rests us).")


if __name__ == "__main__":
    main()
