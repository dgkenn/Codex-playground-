"""Fair-value model for "BTC Up in the next N seconds" binary prediction markets.

A 15-minute "Up/Down" window resolves UP iff the spot price at the window *end*
is strictly greater than the spot price at the window *open*. At any instant t
inside the window we know:

    S0   = spot at the window open      (fixed once the window has started)
    St   = current spot
    tau  = seconds remaining until the window closes

Model the future log-return over the remaining tau seconds as a driftless
Gaussian with per-second volatility ``sigma``:

    log(S_T / St)  ~  Normal(0, sigma^2 * tau)

The window resolves UP iff  S_T > S0, i.e. iff the future increment exceeds
-log(St/S0). Therefore

    p_up = P(increment > -log(St/S0))
         = Phi( log(St/S0) / (sigma * sqrt(tau)) )

Properties (these are what ``validate.py`` checks):
  * At/just before the open (St == S0, tau == window) this is Phi(0) = 0.50, so
    the model is ~0.50 "pre-window" by construction -- it has no opinion before
    any move has happened.
  * As tau -> 0 it collapses to the realized indicator: 1 if St>S0, 0 if St<S0,
    0.5 on an exact tie.
  * If the spot really follows driftless GBM with this sigma, the model is
    perfectly calibrated, so empirical calibration error -> 0 (finite-sample
    noise leaves ~0.01).

This module is intentionally tiny and dependency-light (numpy + scipy) so it can
be reused unchanged by the synthetic validators and by the real backtest.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm


def fair_up(st, s0, sigma_per_s, tau_s):
    """Model probability that a window resolves UP.

    All arguments broadcast; returns a float (scalar in -> float out, array in
    -> ndarray out). ``sigma_per_s`` is the per-second volatility of log spot.
    """
    st = np.asarray(st, dtype=float)
    s0 = np.asarray(s0, dtype=float)
    tau = np.asarray(tau_s, dtype=float)
    sigma = float(sigma_per_s)

    m = np.log(st / s0)                       # realized log-move from the open
    denom = sigma * np.sqrt(np.maximum(tau, 0.0))

    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(denom > 0, m / denom, 0.0)
    p = norm.cdf(z)

    # tau == 0 (or sigma == 0): collapse to the realized indicator.
    collapsed = np.where(m > 0, 1.0, np.where(m < 0, 0.0, 0.5))
    p = np.where(denom > 0, p, collapsed)

    out = np.clip(p, 0.0, 1.0)
    return float(out) if out.ndim == 0 else out


def realized_vol_per_s(prices, dt_s):
    """Per-second log-return volatility from a price series sampled every dt_s s.

    sigma_per_s = std(1-step log returns) / sqrt(dt_s).
    """
    p = np.asarray(prices, dtype=float)
    p = p[np.isfinite(p) & (p > 0)]
    if p.size < 3:
        raise ValueError("need >=3 positive prices to estimate volatility")
    r = np.diff(np.log(p))
    return float(np.std(r, ddof=1) / np.sqrt(dt_s))


def fee_per_share(price, fee_bps):
    """Polymarket-style symmetric trading fee per share.

    Polymarket's CLOB charges a fee proportional to the number of shares and to
    ``min(price, 1 - price)`` -- largest near 0.50, near-zero at the extremes:

        fee = (fee_bps / 10_000) * min(price, 1 - price)

    (This is an explicit modelling assumption; verify against current docs.)
    """
    price = np.asarray(price, dtype=float)
    f = (fee_bps / 10_000.0) * np.minimum(price, 1.0 - price)
    return float(f) if f.ndim == 0 else f
