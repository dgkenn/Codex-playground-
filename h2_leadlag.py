"""H2 stage 1 (signal, not tradeability): does BTC's move within a 15-min window
predict an alt's FUTURE move in the same window, beyond the alt's own move?

If BTC leads the alts, then at time t the BTC return so far (open->t) should
predict the alt's remaining return (t->close) after controlling for the alt's own
return so far. One observation per window (independent -> honest t-stat). If the
BTC coefficient isn't significant, there is no lead-lag signal to trade and H2 is
dead before any order-book fetch.
"""
from __future__ import annotations

import numpy as np

import run_real as rr


def ols_t(y, X):
    """Return coefficients and their t-stats for y = X beta."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    s2 = (resid @ resid) / (n - k)
    xtx_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(s2 * xtx_inv))
    return beta, beta / se


def main():
    btc_ts, btc = rr.load_spot("btc.npz")
    t0 = (btc_ts.min() // 1000 // 900 + 1) * 900
    t1 = btc_ts.max() // 1000 // 900 * 900
    starts = np.arange(t0, t1, 900, dtype=np.int64)
    print(f"windows: {len(starts)}  ({len(starts)} per coin, one obs each)\n")

    for coin in ["ETHUSDT", "SOLUSDT", "XRPUSDT"]:
        a_ts, a = rr.load_spot(coin + ".npz")
        print(f"=== {coin}: alt_future_ret(t->close) ~ alt_past_ret(open->t) + btc_past_ret(open->t) ===")
        print(f"  {'tau':>5} {'n':>4} | {'btc_coef':>9} {'btc_t':>7} | "
              f"{'alt_coef':>9} {'alt_t':>7} | sign(btc)->sign(altfut) hit")
        for tau in (600, 450, 300, 180, 120, 60):
            t = starts + (900 - tau)
            bo = rr.spot_at(btc_ts, btc, starts * 1000); bt = rr.spot_at(btc_ts, btc, t * 1000)
            ao = rr.spot_at(a_ts, a, starts * 1000); at_ = rr.spot_at(a_ts, a, t * 1000)
            ac = rr.spot_at(a_ts, a, (starts + 900) * 1000)
            ok = np.isfinite(bo) & np.isfinite(bt) & np.isfinite(ao) & np.isfinite(at_) & np.isfinite(ac)
            bo, bt, ao, at_, ac = bo[ok], bt[ok], ao[ok], at_[ok], ac[ok]
            btc_past = np.log(bt / bo)
            alt_past = np.log(at_ / ao)
            alt_future = np.log(ac / at_)
            X = np.column_stack([np.ones_like(btc_past), alt_past, btc_past])
            beta, tvals = ols_t(alt_future, X)
            # directional hit rate (only where btc moved meaningfully)
            mv = np.abs(btc_past) > np.percentile(np.abs(btc_past), 50)
            hit = (np.sign(btc_past[mv]) == np.sign(alt_future[mv])).mean()
            print(f"  {tau:5d} {ok.sum():4d} | {beta[2]:+9.3f} {tvals[2]:+7.2f} | "
                  f"{beta[1]:+9.3f} {tvals[1]:+7.2f} | {hit:.3f}")
        print()


if __name__ == "__main__":
    main()
