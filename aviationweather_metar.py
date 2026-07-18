#!/usr/bin/env python3
"""aviationweather_metar.py -- REAL-TIME METAR obs feed for the K-WX weather-nowcast gate.

WHY THIS EXISTS (node KALSHI-WX-ORDERBOOK / KALSHI-WX-CLIBASIS): the forward paper gate was built on
the IEM asos1min *archive*, which LAGS 1-2 days -> it cannot fire live. And the confirmed tail-shrink
(KALSHI-WX-CLIBASIS) requires an *independent published* obs that reaches the bare strike before we
trade. Published METAR from aviationweather.gov solves BOTH: it is free, real-time (current cycle +
SPECIs, 15-day rolling history), and is the same family NWS reconciles the CLI daily-max against.

Kalshi KXHIGH/KXLOW settle on the NWS CLI daily max/min for ONE ASOS station per city, whole degF,
strictly '>', on the LOCAL-STANDARD-TIME day (never DST). This module returns published-METAR temps
for a station over an LST day and the running max/min -- the independent "confirmation" signal.

Temperature precision: aviationweather's JSON `temp` field is decoded from the METAR, preferring the
RMK T-group (tenths of degC) over the whole-degC body group when present -> ~0.1 degC resolution, which
is finer than the whole-degF settlement grid. We convert C->F and keep tenths.

Resolution/latency caveat vs 1-min ASOS: METAR is ~hourly (routine) + SPECIs on significant change, NOT
1-min. So it is a SLOWER but INDEPENDENT and REAL-TIME confirmation -- exactly the gate role. The fast
trigger still comes from 1-min ASOS/HF; METAR is the withhold-until-confirmed check + the live fallback.

READ-ONLY public API. stdlib only. PROPOSE-ONLY (no orders here).

Usage:
  python aviationweather_metar.py KDEN                 # last 24h temps + running max/min (degF)
  python aviationweather_metar.py KDEN 2026-07-17 -7   # running max/min for one LST day (offset hrs)
"""
import urllib.request, json, ssl, os, sys, datetime as dt

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_API = "https://aviationweather.gov/api/data/metar"

# NYC/Central Park special-case: Kalshi settles NYC on the Central Park COOP site. The nearest METAR
# with the same microclimate is KNYC (Central Park ASOS). aviationweather serves KNYC.
_STATION_ALIAS = {"NYC": "KNYC"}


def _c_to_f(c):
    return c * 9.0 / 5.0 + 32.0


def fetch_metar(station, hours=24, timeout=30):
    """Return list of dicts {time: aware-UTC datetime, temp_f: float, raw: str} sorted ascending.

    `station` may be an IEM-style id (e.g. 'NYC') -- aliased to its ICAO METAR id. `hours` is how far
    back to pull from the rolling window (aviationweather supports the current 15-day window)."""
    sid = _STATION_ALIAS.get(station, station)
    if len(sid) == 3 and not sid.startswith("K"):
        sid = "K" + sid  # 3-letter US ids -> ICAO K-prefixed
    url = f"{_API}?ids={sid}&format=json&hours={int(hours)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "wx-research"})
    data = json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
    out = []
    for r in data:
        t = r.get("temp")
        ts = r.get("reportTime") or r.get("obsTime")
        if t is None or ts is None:
            continue
        try:
            # reportTime like '2026-07-18T18:00:00.000Z' or epoch seconds in obsTime
            if isinstance(ts, (int, float)):
                when = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
            else:
                when = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        out.append({"time": when, "temp_f": _c_to_f(float(t)), "raw": r.get("rawOb", "")})
    out.sort(key=lambda x: x["time"])
    return out


def lst_day_window_utc(lst_date, offset_hours):
    """The [start,end) UTC datetimes bounding one LOCAL-STANDARD-TIME calendar day.

    lst_date: 'YYYY-MM-DD' (the LST day). offset_hours: fixed standard-time UTC offset (e.g. -7 for
    Denver MST) -- NEVER DST-adjusted, matching Kalshi settlement."""
    d = dt.date.fromisoformat(lst_date) if isinstance(lst_date, str) else lst_date
    start_local = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=dt.timezone.utc)
    # local midnight in UTC = local_midnight - offset  (offset is local = UTC + offset)
    start_utc = start_local - dt.timedelta(hours=offset_hours)
    return start_utc, start_utc + dt.timedelta(hours=24)


def running_extreme_for_lst_day(station, lst_date, offset_hours, kind="max", hours=None):
    """Published-METAR running max (or min) degF over one LST day, plus the confirming obs.

    Returns dict: {extreme_f, n_obs, first_time, last_time, obs:[(time,temp_f)...]} or None if no obs.
    `kind`='max' for KXHIGH, 'min' for KXLOW. Auto-sizes the fetch window to cover the day if hours
    unset (useful for recent/live days; for older days within the 15-day window pass hours explicitly)."""
    start_utc, end_utc = lst_day_window_utc(lst_date, offset_hours)
    if hours is None:
        # cover from day-start to now (+margin); METAR window is 15 days
        now = dt.datetime.now(tz=dt.timezone.utc) if False else None  # Date.now unavailable in some sandboxes
        # fetch a generous window and filter; 48h back from end covers a full LST day robustly
        hours = 48
    obs = [o for o in fetch_metar(station, hours=hours) if start_utc <= o["time"] < end_utc]
    if not obs:
        return None
    temps = [o["temp_f"] for o in obs]
    ext = max(temps) if kind == "max" else min(temps)
    return {
        "extreme_f": ext,
        "n_obs": len(obs),
        "first_time": obs[0]["time"].isoformat(),
        "last_time": obs[-1]["time"].isoformat(),
        "obs": [(o["time"].isoformat(), round(o["temp_f"], 2)) for o in obs],
    }


def metar_confirms_strike(station, lst_date, offset_hours, strike_f, kind="max", hours=None):
    """The KALSHI-WX-CLIBASIS confirmation gate: has published METAR *independently* reached the bare
    strike? For KXHIGH ('> strike'): running max must exceed strike. For KXLOW ('< strike'): running
    min must fall below strike. Returns (confirmed: bool, observed_extreme_f: float|None)."""
    r = running_extreme_for_lst_day(station, lst_date, offset_hours, kind=kind, hours=hours)
    if r is None:
        return False, None
    ext = r["extreme_f"]
    return (ext > strike_f if kind == "max" else ext < strike_f), ext


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else "KDEN"
    if len(sys.argv) >= 4:
        date_s, off = sys.argv[2], float(sys.argv[3])
        for kind in ("max", "min"):
            r = running_extreme_for_lst_day(st, date_s, off, kind=kind)
            if r:
                print(f"{st} {date_s} LST running {kind}: {r['extreme_f']:.1f}F over {r['n_obs']} obs "
                      f"({r['first_time']} -> {r['last_time']})")
            else:
                print(f"{st} {date_s} LST running {kind}: NO OBS in window")
    else:
        obs = fetch_metar(st, hours=24)
        if not obs:
            print(f"{st}: no METAR obs")
        else:
            temps = [o["temp_f"] for o in obs]
            print(f"{st}: {len(obs)} obs last 24h | running max={max(temps):.1f}F min={min(temps):.1f}F")
            for o in obs[-6:]:
                print(f"  {o['time'].isoformat()}  {o['temp_f']:.1f}F   {o['raw'][:60]}")
