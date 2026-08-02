#!/usr/bin/env python3
"""wx_forecast_model.py -- the FORECAST-edge predictive model for Kalshi daily high/low temp markets.

WHY (state the hypothesis honestly): the K-WX nowcast bot only trades AFTER the day's extreme is mechanically
locked in the live obs -- pure settlement mechanics, near-zero forecast risk. This is a DIFFERENT, riskier
edge: use a free NWP forecast (Open-Meteo GFS/HRRR blend) to predict a city's daily max/min BEFORE it happens,
turn that point forecast into a predictive distribution (realized ~ Normal(mu, sigma)), and compute P(the
official ASOS settlement lands in each Kalshi bracket). Where our forecast_prob disagrees with the market's
yes-price by more than a threshold, that's a candidate trade.

The catch, stated up front: the Kalshi market makers see the SAME free Open-Meteo forecast we do. So an edge
only exists if OUR distribution is better-calibrated than the price the crowd has already set -- e.g. the
market is slow to move, mis-sizes the forecast uncertainty, or leaves stale quotes on thin rungs. This module
does NOT assume that gap is real; it just produces forecast_prob so the forward harness (wx_forecast_forward.py)
can MEASURE whether forecast_prob - price actually predicts realized pnl. If the market already tracks the
forecast tightly, there is no edge and the harness should say so.

Settlement convention -- DERIVED FROM DATA, 2026-08-02 (FIX 3; see FIX_SPEC.md / livefix_selftest.py for the
full per-shape disagreement table against Kalshi's official `result` field, 616-row wx_forecast_settled.jsonl):
    - full bracket (floor F, cap C, both set): INCLUSIVE on BOTH ends -- YES iff F <= X <= C. Kalshi's
      bracket includes its floor. The old exclusive-floor convention (F < X <= C, "mirroring Kalshi's '>'
      settlement") mis-scored 24.4% of full-bracket rows, every miscall the same shape (X==F, we said NO,
      Kalshi said YES); the inclusive-floor convention drops that to 7.6% (residual is a same-week IEM
      data-revision-lag artifact in the most recent days of the sample, NOT a boundary/convention effect --
      see the module-level note in wx_forecast_forward._bracket_won).
    - top rung (cap=None, floor F only): UNCHANGED, exclusive floor -- YES iff X > F. This already matched
      best in the data (1.5% disagreement vs 13.6% for the inclusive X>=F candidate) -- do not "fix" what
      isn't broken here.
    - cap-only rung (floor=None, cap C only): EXCLUSIVE cap -- YES iff X < C (not X<=C). The old X<=C
      convention mis-scored 23.4% of cap-only rows, every boundary miscall the same shape (X==C, we said
      YES, Kalshi said NO); X<C drops that to 8.5% (again, residual is the same data-lag artifact).
bracket_prob mirrors this exactly, via a half-degree continuity correction (see its docstring) since the
settlement data is whole-degF.

stdlib + numpy/scipy only. No credentials, no orders. TLS via the session CA bundle.

Usage:
    python wx_forecast_model.py        # print a couple cities' forecast + a sample bracket_prob table
"""
import os, ssl, json, datetime as dt, urllib.request, urllib.parse
from scipy.stats import norm

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
OM_BASE = "https://api.open-meteo.com/v1/forecast"

# --- predictive-distribution width (forecast-vs-ASOS dispersion). Top-of-file constants so they can be
# RECALIBRATED once the harness has collected forecast/realized pairs (compute the residual std per kind and
# drop it in here). CALIBRATED 2026-07 from an 8-station x 45-day lead-0 (same-day, morning-of) backtest vs IEM
# ASOS truth (n=360 max / 359 min): after removing the systematic max cold bias below, the max residual std is
# ~1.17F, so SIGMA_MAX=1.2 (was a 2.0 placeholder -- too wide, it under-fired +EV rungs). MIN is left at 2.0:
# its residual is only tightenable (2.09->1.62) via a PER-STATION de-bias we don't apply globally (min biases
# cancel across stations), so tightening min sigma without that de-bias would be overconfident. The harness
# trades morning HIGHS, so the max calibration is the one that drives EV. CAVEAT: summer-only fit; re-derive
# per season and, preferably, from the harness's OWN accumulating settled residuals as they build up. ---
SIGMA_MAX = 1.2   # degF: std of (realized daily max - BIAS-CORRECTED forecast max), lead-0; from the 2026-07 fit
SIGMA_MIN = 2.0   # degF: uncorrected min residual (~2.09); left wide -- see note above (no global min de-bias)
# crude lead-time inflation (uncertainty grows with lead); identity at lead 0-1d until recalibrated.
_LEAD_INFLATE = {0: 1.0, 1: 1.0, 2: 1.25, 3: 1.5}

# --- systematic forecast-vs-sensor bias correction (added to the raw Open-Meteo mu). MEASURED 2026-07: the
# gfs_seamless daily max runs ~1.09F COLD at these airport points (bias = forecast - truth = -1.09), a stable
# grid-vs-station representativeness effect (leave-one-out == in-sample to ~0.02F, so it's structural, not
# overfit). Correcting it moves prob mass to the correct rung (e.g. a true-90F day: winning-rung P 0.416->0.558).
# MIN global bias is ~0 (-0.09; station-specific biases cancel), so no global min correction is applied. ---
BIAS_MAX_CORRECTION = 1.09   # degF added to the raw forecast max (warms the cold bias out)
BIAS_MIN_CORRECTION = 0.0    # degF: global min bias ~0; would need a per-station table (not applied)


def predictive_sigma(kind, lead_days=0):
    """Predictive std (degF) for a max ('max') or min forecast at the given forecast lead. Constant base per
    kind (SIGMA_MAX/SIGMA_MIN) times a mild lead inflation. RECALIBRATE the bases from collected residuals."""
    base = SIGMA_MAX if kind == "max" else SIGMA_MIN
    return base * _LEAD_INFLATE.get(max(0, int(lead_days)), 1.5)


# station -> (latitude, longitude, IANA timezone, IEM ASOS network). Stations come from kwx_runner.CITY; coords
# are the well-known airport locations (Central Park 'NYC' for the KXHIGHNY series). IEM ids drop the leading K
# (DEN, MIA, ...); network is the state ASOS net (DCA is physically in Virginia -> VA_ASOS; NYC -> NY_ASOS).
STATIONS = {
    "KDEN": (39.8617, -104.6731, "America/Denver",      "CO_ASOS"),
    "KMIA": (25.7959,  -80.2870, "America/New_York",    "FL_ASOS"),
    "KMDW": (41.7860,  -87.7524, "America/Chicago",     "IL_ASOS"),
    "KBOS": (42.3656,  -71.0096, "America/New_York",    "MA_ASOS"),
    "KAUS": (30.1975,  -97.6664, "America/Chicago",     "TX_ASOS"),
    "KSEA": (47.4502, -122.3088, "America/Los_Angeles", "WA_ASOS"),
    "KSFO": (37.6213, -122.3790, "America/Los_Angeles", "CA_ASOS"),
    "KMSP": (44.8848,  -93.2223, "America/Chicago",     "MN_ASOS"),
    "KDCA": (38.8512,  -77.0402, "America/New_York",    "VA_ASOS"),
    "KATL": (33.6407,  -84.4277, "America/New_York",    "GA_ASOS"),
    "KDFW": (32.8998,  -97.0403, "America/Chicago",     "TX_ASOS"),
    "KSAT": (29.5337,  -98.4698, "America/Chicago",     "TX_ASOS"),
    "NYC":  (40.7789,  -73.9692, "America/New_York",    "NY_ASOS"),
    "KOKC": (35.3931,  -97.6007, "America/Chicago",     "OK_ASOS"),
    "KLAS": (36.0840, -115.1537, "America/Los_Angeles", "NV_ASOS"),
    "KPHX": (33.4342, -112.0116, "America/Phoenix",     "AZ_ASOS"),
    "KHOU": (29.6454,  -95.2789, "America/Chicago",     "TX_ASOS"),
    "KPHL": (39.8729,  -75.2437, "America/New_York",    "PA_ASOS"),
    "KMSY": (29.9934,  -90.2580, "America/Chicago",     "LA_ASOS"),
    "KLAX": (33.9416, -118.4085, "America/Los_Angeles", "CA_ASOS"),
}


def iem_station(station):
    """ASOS id used by the IEM daily CSV (drop the leading K; NYC has none)."""
    return station[1:] if station.startswith("K") and len(station) == 4 else station


def _get(url, to=25):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=to, context=_CTX))


def fetch_forecast(station, date=None, forecast_days=3):
    """Fetch the Open-Meteo daily max/min forecast for `station`. Returns
    {'max': mu_max, 'min': mu_min, 'issued': iso_utc, 'date': local_date, 'lead_days': n} for the requested
    LOCAL date (default: today in the station's tz). 'issued' is the wall-clock UTC fetch time -- the forward
    harness logs the forecast at snapshot time, so by construction it was issued before any settlement we
    later score (no look-ahead). Returns None if the station is unknown or the date is not in the horizon."""
    if station not in STATIONS:
        return None
    lat, lon, tz, _ = STATIONS[station]
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit", "timezone": tz,
        "forecast_days": max(1, int(forecast_days)),
    })
    d = _get(f"{OM_BASE}?{q}")
    daily = d.get("daily", {})
    days = daily.get("time", [])
    mx, mn = daily.get("temperature_2m_max", []), daily.get("temperature_2m_min", [])
    if not days:
        return None
    target = date or days[0]                     # default: today's local date (first horizon day)
    if target not in days:
        return None
    i = days.index(target)
    if i >= len(mx) or i >= len(mn) or mx[i] is None or mn[i] is None:
        return None
    return {
        # apply the measured systematic bias correction so the mu points at the right rung (see BIAS_* notes).
        "max": float(mx[i]) + BIAS_MAX_CORRECTION, "min": float(mn[i]) + BIAS_MIN_CORRECTION,
        "issued": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "date": target, "lead_days": days.index(target),
    }


def forecast_for(station, date):
    """Convenience: forecast for a specific local date string (YYYY-MM-DD) within the 3-day horizon."""
    return fetch_forecast(station, date=date)


def bracket_prob(lo, hi, mu, sigma):
    """P(settlement lands in the rung), under the CONTINUOUS X ~ Normal(mu, sigma), matching the
    DATA-DERIVED discrete settlement convention (FIX 3, see module docstring):
        - full bracket (lo, hi both set) : YES iff lo <= X_int <= hi   (inclusive both ends)
        - cap-only rung (lo=None)        : YES iff X_int < hi          (exclusive cap)
        - top rung (hi=None)             : YES iff X_int > lo          (exclusive floor, unchanged)

    HALF-DEGREE CONTINUITY CORRECTION: the actual settlement (X_int) is a WHOLE degF integer, but we score
    it against a continuous Normal. Naively plugging the integer discrete boundaries into the continuous
    CDF (e.g. cdf(hi) - cdf(lo) for an inclusive bracket) would UNDER-count: the inclusive endpoint's own
    unit-width mass needs to be attributed to this rung. The standard fix is to treat each integer k as
    representing the continuous interval [k-0.5, k+0.5) (or the appropriate half thereof at a boundary) and
    integrate over the UNION of those intervals for every integer this rung's discrete rule includes:
        - full bracket [lo, hi] inclusive-inclusive -> continuous interval [lo-0.5, hi+0.5]
          (integers lo, lo+1, ..., hi are each covered by their own +-0.5 half-open cell; those cells tile
          the range with no gap and no overlap)
        - cap-only, X_int < hi (integers ..., hi-2, hi-1) -> continuous interval (-inf, hi-0.5]
          (hi itself is EXCLUDED, so the correction stops half a degree BELOW hi, not above it)
        - top rung, X_int > lo (integers lo+1, lo+2, ...) -> continuous interval [lo+0.5, +inf)
          (lo itself is EXCLUDED, so the correction starts half a degree ABOVE lo)

    ADJACENCY CHECK (no double-count, no gap): two consecutive full brackets [lo, lo+1] and [lo+2, lo+3]
    (Kalshi's brackets are 2 whole degrees wide, e.g. floor=97/cap=98 then floor=99/cap=100) map to
    continuous intervals [lo-0.5, lo+1.5] and [lo+1.5, lo+3.5] -- they meet EXACTLY at lo+1.5 with zero
    overlap and zero gap. A top rung with floor=lo+3 immediately above that ladder maps to
    [lo+3.5, +inf), which again picks up exactly where the last full bracket's continuous interval left
    off. So the half-degree shift is consistent across the whole ladder, not just within one rung.
    """
    if sigma <= 0:
        sigma = 1e-6
    if lo is not None and hi is not None:
        lo_b, hi_b = lo - 0.5, hi + 0.5          # full bracket: inclusive both ends
    elif lo is None and hi is not None:
        lo_b, hi_b = None, hi - 0.5              # cap-only: exclusive cap
    elif hi is None and lo is not None:
        lo_b, hi_b = lo + 0.5, None              # top rung: exclusive floor (unchanged shape)
    else:
        lo_b, hi_b = None, None                  # no bound at all (shouldn't occur) -> unconstrained
    plo = norm.cdf(lo_b, mu, sigma) if lo_b is not None else 0.0
    phi = norm.cdf(hi_b, mu, sigma) if hi_b is not None else 1.0
    return float(max(0.0, min(1.0, phi - plo)))


def ladder_probs(rungs, kind, mu, sigma):
    """Given kwx_runner.event_rungs output for one event, attach fc_prob to each rung. kind in {'max','min'}
    only selects which mu/sigma the caller passed; the bracket math is identical (floor=lo, cap=hi)."""
    out = []
    for r in rungs:
        p = bracket_prob(r.get("floor"), r.get("cap"), mu, sigma)
        out.append({**r, "fc_prob": p})
    return out


def _demo():
    """Print a couple cities' forecast and a sample bracket_prob table (sanity check on coords/plausibility)."""
    for stn in ("KDEN", "KMIA", "KPHX"):
        fc = fetch_forecast(stn)
        if not fc:
            print(f"{stn}: no forecast"); continue
        print(f"\n{stn}  {fc['date']} (lead {fc['lead_days']}d)  forecast max={fc['max']:.1f}F min={fc['min']:.1f}F")
        mu, sig = fc["max"], predictive_sigma("max", fc["lead_days"])
        print(f"   sample MAX brackets around mu={mu:.1f}, sigma={sig:.1f}:")
        base = round(mu)
        for lo, hi in [(None, base - 3), (base - 3, base - 1), (base - 1, base + 1),
                       (base + 1, base + 3), (base + 3, None)]:
            lbl = f"({'  -inf' if lo is None else f'{lo:>5}'}, {'+inf ' if hi is None else f'{hi:>4}'}]"
            print(f"      {lbl}  P = {bracket_prob(lo, hi, mu, sig):.3f}")


if __name__ == "__main__":
    _demo()
