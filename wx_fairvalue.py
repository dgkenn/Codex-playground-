#!/usr/bin/env python3
"""wx_fairvalue.py -- calibrated fair-value engine for Kalshi daily-HIGH temperature markets.

This is the reusable model the trading layer calls. Given a forecast distribution for a
city/day, it returns P(integer daily high in each Kalshi bracket), with a +/-0.5 F rounding
correction (NWS CLI reports whole degrees; Kalshi "85 to 86" = high in {85,86}).

Three candidate distribution models are exposed; calibration testing (wx_calibrate.py) picks
the winner. All take only information available at trade time (no lookahead).

  (a) normal_probs   -- Normal(mu=forecast_high + bias, sigma) ; sigma from historical error.
  (b) ensemble_probs -- empirical CDF over ensemble members (GEFS), bias-corrected; usually
                        better-calibrated than a fixed-sigma Normal because spread is flow/regime
                        dependent. Falls back to (a) if too few members.
  (c) skewt_probs    -- bias-corrected skew-t (skew + fat tails) ; temp errors are mildly skewed.

Stations match Kalshi settlement (Central Park KNYC, Chicago Midway KMDW, Austin Camp Mabry
KATT, etc.). See STATIONS.

Ground truth for settlement = NWS station daily high (we proxy with IEM ASOS max_tmpf, which is
the obs feed NWS CLI is built from; ERA5 reanalysis is NOT used as truth -- it carries a multi-F
urban cool bias, e.g. Central Park 2024-06-03 ERA5 85.3 vs station 86).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
from scipy.stats import norm, skewnorm

# ----------------------------------------------------------------------------------------------
# City -> settlement station metadata. (lat,lon) feed Open-Meteo at the Kalshi settlement point;
# IEM (id, network) feed the realized station high.
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Station:
    city: str
    kalshi_series: str
    nws_id: str          # NWS/ICAO id (settlement station)
    lat: float
    lon: float
    iem_id: str          # IEM ASOS id (truth source)
    iem_network: str

STATIONS = {
    'NYC': Station('NYC', 'KXHIGHNY',   'KNYC', 40.7790, -73.9693, 'NYC', 'NY_ASOS'),  # Central Park
    'CHI': Station('CHI', 'KXHIGHCHI',  'KMDW', 41.7860, -87.7524, 'MDW', 'IL_ASOS'),  # Midway
    'MIA': Station('MIA', 'KXHIGHMIA',  'KMIA', 25.7906, -80.3164, 'MIA', 'FL_ASOS'),  # Miami Intl
    'AUS': Station('AUS', 'KXHIGHAUS',  'KATT', 30.3206, -97.7600, 'ATT', 'TX_ASOS'),  # Camp Mabry
    'LAX': Station('LAX', 'KXHIGHLAX',  'KLAX', 33.9381, -118.3892,'LAX', 'CA_ASOS'),  # LAX
    'PHX': Station('PHX', 'KXHIGHTPHX', 'KPHX', 33.4278, -112.0037,'PHX', 'AZ_ASOS'),  # Phoenix
    'DAL': Station('DAL', 'KXHIGHTDAL', 'KDFW', 32.8978, -97.0189, 'DFW', 'TX_ASOS'),  # DFW
    'BOS': Station('BOS', 'KXHIGHTBOS', 'KBOS', 42.3606, -71.0097, 'BOS', 'MA_ASOS'),  # Logan
}

# ----------------------------------------------------------------------------------------------
# Bracket integration helpers (shared by all models). Kalshi interior bins are 2 F wide; tails
# are open. A bracket is the set of integer highs in [lo,hi]; we integrate the continuous
# distribution over [lo-0.5, hi+0.5] to honor whole-degree rounding.
# ----------------------------------------------------------------------------------------------
def _cont_bounds(lo: Optional[int], hi: Optional[int]):
    a = (lo - 0.5) if lo is not None else -1e9
    b = (hi + 0.5) if hi is not None else 1e9
    return a, b


def normal_probs(brackets, mu, sigma):
    """(a) Normal model. brackets: list of (lo,hi) integer bounds (None = open tail)."""
    sigma = max(float(sigma), 0.5)
    out = []
    for lo, hi in brackets:
        a, b = _cont_bounds(lo, hi)
        out.append(float(norm.cdf(b, mu, sigma) - norm.cdf(a, mu, sigma)))
    return np.array(out)


def ensemble_probs(brackets, members, bias=0.0, smooth=0.6, min_members=8):
    """(b) Ensemble model. members: array of per-member forecast highs (F).
    Empirical CDF with a small Gaussian kernel (bandwidth `smooth` F) so a finite member count
    yields smooth bracket probabilities and non-zero tails. bias is subtracted (mean error)."""
    m = np.asarray(members, dtype=float)
    m = m[np.isfinite(m)]
    if m.size < min_members:
        mu = (np.mean(m) - bias) if m.size else 0.0
        sd = np.std(m, ddof=1) if m.size > 1 else 3.0
        return normal_probs(brackets, mu, max(sd, 1.5))
    m = m - bias
    bw = max(smooth, 0.5)
    out = []
    for lo, hi in brackets:
        a, b = _cont_bounds(lo, hi)
        # kernel-smoothed empirical CDF: average per-member Normal(member, bw) mass in [a,b]
        p = np.mean(norm.cdf(b, m, bw) - norm.cdf(a, m, bw))
        out.append(float(p))
    out = np.array(out)
    s = out.sum()
    return out / s if s > 0 else out


def skewt_probs(brackets, mu, sigma, skew=0.0):
    """(c) Skew-Normal model (skew + slightly heavier shoulders than Normal). skew = scipy 'a'.
    skew>0 = warm (right) tail heavier -- matches the recreational warm-tail story if real."""
    sigma = max(float(sigma), 0.5)
    if abs(skew) < 1e-3:
        return normal_probs(brackets, mu, sigma)
    # convert (location mu = desired mean, sigma = desired sd) for skewnorm
    a = skew
    delta = a / math.sqrt(1 + a * a)
    scale = sigma / math.sqrt(1 - 2 * delta * delta / math.pi)
    loc = mu - scale * delta * math.sqrt(2 / math.pi)
    out = []
    for lo, hi in brackets:
        lb, ub = _cont_bounds(lo, hi)
        out.append(float(skewnorm.cdf(ub, a, loc, scale) - skewnorm.cdf(lb, a, loc, scale)))
    out = np.array(out)
    s = out.sum()
    return out / s if s > 0 else out


# ----------------------------------------------------------------------------------------------
# The single entry point the trading layer should call.
# ----------------------------------------------------------------------------------------------
@dataclass
class FairValueParams:
    """Per-city/season/lead calibrated parameters (fit by wx_calibrate.py)."""
    bias: float = 0.0       # mean(forecast - actual); subtract from forecast
    sigma: float = 3.0      # residual sd after bias correction (the bracket WIDTH driver)
    skew: float = 0.0       # skew-normal shape; 0 = Normal
    model: str = 'ensemble' # 'normal' | 'ensemble' | 'skewt'


def fair_value(brackets, forecast_high, params: FairValueParams,
               members: Optional[Sequence[float]] = None):
    """Return P(high in each bracket) for the chosen calibrated model.

    brackets : list of (lo,hi) integer bounds, None for open tails (Kalshi order).
    forecast_high : deterministic point forecast (ensemble mean or model high), in F.
    params : calibrated FairValueParams for this city/season/lead.
    members : ensemble member highs (required for model='ensemble').
    """
    mu = forecast_high - params.bias
    if params.model == 'ensemble' and members is not None and len(members) >= 8:
        return ensemble_probs(brackets, members, bias=params.bias)
    if params.model == 'skewt':
        return skewt_probs(brackets, mu, params.sigma, params.skew)
    return normal_probs(brackets, mu, params.sigma)


# Convenience: build standard Kalshi bracket list around a center (2F interior bins + open tails).
def standard_brackets(center, n_each_side=3, width=2):
    """Mimic a Kalshi event ladder: open-low tail, 2F bins, open-high tail (for offline testing)."""
    lo0 = int(round(center)) - n_each_side * width
    brs = [(None, lo0 - 1)]
    x = lo0
    for _ in range(2 * n_each_side):
        brs.append((x, x + width - 1))
        x += width
    brs.append((x, None))
    return brs


if __name__ == '__main__':
    p = FairValueParams(bias=0.0, sigma=2.5, model='normal')
    brs = standard_brackets(80)
    print('brackets:', brs)
    print('normal  :', np.round(normal_probs(brs, 80, 2.5), 3))
    mem = list(np.random.default_rng(0).normal(80, 2.5, 31))
    print('ensemble:', np.round(ensemble_probs(brs, mem), 3))
    print('skewt+2 :', np.round(skewt_probs(brs, 80, 2.5, 2.0), 3))
