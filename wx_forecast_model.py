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

Settlement convention (mirrors kwx_runner): Kalshi temp rungs settle strictly '>' on whole degF. A rung with
floor F, cap C settles YES iff F < settlement <= C; a cap-only rung (floor=None) is YES iff X <= C; a
floor-only top rung (cap=None) is YES iff X > F. bracket_prob mirrors that exactly with the Normal CDF.

stdlib + numpy/scipy only. No credentials, no orders. TLS via the session CA bundle.

Usage:
    python wx_forecast_model.py        # print a couple cities' forecast + a sample bracket_prob table
"""
import os, ssl, json, datetime as dt, urllib.request, urllib.parse
from scipy.stats import norm

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
OM_BASE = "https://api.open-meteo.com/v1/forecast"

# --- predictive-distribution width (day-ahead forecast-vs-ASOS dispersion). Top-of-file constants so they can
# be RECALIBRATED once the harness has collected forecast/realized pairs (compute the residual std per kind and
# drop it in here). 2.0F is a deliberately-honest day-ahead starting point for a GFS/HRRR daily max/min; too
# small and every rung looks mispriced, too large and nothing does. sigma is what makes or breaks the edge. ---
SIGMA_MAX = 2.0   # degF: std of (realized daily max - forecast max), ~day-ahead lead
SIGMA_MIN = 2.0   # degF: std of (realized daily min - forecast min), ~day-ahead lead
# crude lead-time inflation (uncertainty grows with lead); identity at lead 0-1d until recalibrated.
_LEAD_INFLATE = {0: 1.0, 1: 1.0, 2: 1.25, 3: 1.5}


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
        "max": float(mx[i]), "min": float(mn[i]),
        "issued": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "date": target, "lead_days": days.index(target),
    }


def forecast_for(station, date):
    """Convenience: forecast for a specific local date string (YYYY-MM-DD) within the 3-day horizon."""
    return fetch_forecast(station, date=date)


def bracket_prob(lo, hi, mu, sigma):
    """P(lo < X <= hi) under X ~ Normal(mu, sigma), mirroring Kalshi's '>' settlement:
        - full bracket : lo=floor, hi=cap -> cdf(hi) - cdf(lo)
        - cap-only rung: lo=None         -> cdf(hi)          (P(X <= cap))
        - top rung     : hi=None         -> 1 - cdf(lo)      (P(X > floor))
    (lo, hi are whole-degF strikes; we keep the plain continuous CDF -- no continuity fudge -- so the number
    means exactly 'probability mass in the interval', which is what we compare to the yes-price.)"""
    if sigma <= 0:
        sigma = 1e-6
    plo = norm.cdf(lo, mu, sigma) if lo is not None else 0.0
    phi = norm.cdf(hi, mu, sigma) if hi is not None else 1.0
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
