#!/usr/bin/env python3
"""madis_feed.py -- FREE MADIS hfmetar obs feed for the K-WX runner (a lower-latency free primary).

MADIS (NOAA's Meteorological Assimilation Data Ingest System) publishes the high-frequency METAR/ASOS SPECI
stream on an OPEN public HTTPS tier (no registration, no FTP/LDM): gzipped netCDF, one file per UTC hour, the
current-hour file progressively filled. MEASURED (2026-07-18): 5-minute resolution at ~10-min data latency for
SPECI-reporting stations -- fresher than api.weather.gov (~15-20 min), though NOT the paid 1-min tier (the true
1-minute ASOS / DSI-6405 is not in the free public tier; only Synoptic gives ~1-2 min). So this is a free,
permanent BASELINE improvement, not the 2x capacity jump.

Same interface as WeatherGovFeed/SynopticFeed: running_extreme(station, lst_date, offset, kind) -> running
max/min (degF) over the LST day, glitch-guarded downstream by the runner's sustain=3 filter. Stations that
only report hourly (e.g. KDEN) simply have sparse/no hfmetar obs -> the runner's PrimaryWithFallback falls
back to weather.gov for those. Temperatures are Kelvin in MADIS -> F. NYC -> KNYC (Central Park).

Files:  https://madis-data.ncep.noaa.gov/madisPublic1/data/LDAD/hfmetar/netCDF/YYYYMMDD_HH00.gz
Caching: past-hour files are immutable (cached for the process); the current-hour file is re-fetched at most
once per CURRENT_TTL seconds (it grows as obs arrive). One file carries ALL stations, so a poll cycle over 20
cities downloads each hour once, not per-station.

Usage:
  python madis_feed.py KMIA 2026-07-18 -5           # running max/min for an LST day (degF)
  python madis_feed.py probe KMIA,KLAX,KDEN         # measure per-station resolution + data latency
"""
import urllib.request, ssl, os, sys, gzip, io, time, datetime as dt

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
BASE = "https://madis-data.ncep.noaa.gov/madisPublic1/data/LDAD/hfmetar/netCDF"
_UA = f"kwx-weather-nowcast ({os.environ.get('WX_CONTACT', 'research@example.com')})"
_ALIAS = {"NYC": "KNYC"}
CURRENT_TTL = 60          # re-fetch the still-filling current-hour file at most this often (s)
_MAX_CACHE_HOURS = 40     # prune old parsed-hour entries beyond this (bounds memory in a long run)
_CACHE = {}               # hh_key -> (fetch_epoch, {station: [(utc_dt, temp_f), ...]})


def _sid(station):
    s = _ALIAS.get(station, station)
    return s if (s.startswith("K") or len(s) != 3) else "K" + s


def _parse_hour(nc_bytes):
    """Parse a MADIS hfmetar netCDF -> {station: [(utc_dt, temp_f), ...]}. Kelvin->F, fill/QC-sane only."""
    import scipy.io as sio       # lazy: importing this module never requires scipy until a fetch happens
    import numpy as np
    f = sio.netcdf_file(io.BytesIO(nc_bytes))
    # stationId = the ICAO id (KMIA); stationName is the long name ("MIAMI INTL"). Char arrays are (N, len) |S1.
    names = [row.tobytes().decode("latin1").replace("\x00", "").strip() for row in f.variables["stationId"][:]]
    temps = f.variables["temperature"][:].astype("float64")      # Kelvin
    tobs = f.variables["observationTime"][:].astype("float64")   # epoch seconds
    out = {}
    for nm, tk, ts in zip(names, temps, tobs):
        if not (np.isfinite(tk) and np.isfinite(ts)):
            continue
        if not (1.7e9 < ts < 2.0e9):     # sane epoch (2023..2033); drops MADIS fill values
            continue
        if tk < 200.0 or tk > 340.0:     # sane surface Kelvin (-100F..152F); drops fills/glitches
            continue
        out.setdefault(nm, []).append((dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc),
                                       (tk - 273.15) * 9.0 / 5.0 + 32.0))
    for k in out:
        out[k].sort()
    return out


def _fetch_hour(hh_key, is_current):
    """Return {station: [(dt, tempF)]} for a UTC-hour file, with caching. Past hours cached for the process;
    the current hour honored a short TTL (it's still being appended). Raises on network/parse failure."""
    ent = _CACHE.get(hh_key)
    if ent is not None and (not is_current or (time.time() - ent[0]) < CURRENT_TTL):
        return ent[1]
    url = f"{BASE}/{hh_key}.gz"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": _UA}),
                                 timeout=40, context=_CTX).read()
    parsed = _parse_hour(gzip.decompress(raw))
    _CACHE[hh_key] = (time.time(), parsed)
    if len(_CACHE) > _MAX_CACHE_HOURS:                          # prune oldest keys (lexical == chronological)
        for k in sorted(_CACHE)[:len(_CACHE) - _MAX_CACHE_HOURS]:
            _CACHE.pop(k, None)
    return parsed


def _hours_spanning(start_utc, end_utc):
    h = start_utc.replace(minute=0, second=0, microsecond=0)
    keys = []
    while h <= end_utc:
        keys.append(h.strftime("%Y%m%d_%H00"))
        h += dt.timedelta(hours=1)
    return keys


def _day_obs(station, lst_date, offset):
    """All (utc_dt, temp_f) for `station` within the LST day [start, min(start+24h, now)], across hourly files."""
    d = dt.date.fromisoformat(lst_date) if isinstance(lst_date, str) else lst_date
    start_local = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
    start_utc = start_local - dt.timedelta(hours=offset)
    end_day = start_utc + dt.timedelta(hours=24)
    now = dt.datetime.now(tz=dt.timezone.utc)
    end_utc = min(end_day, now)
    if end_utc < start_utc:
        return []
    sid = _sid(station)
    cur_key = now.strftime("%Y%m%d_%H00")
    obs = []
    for hk in _hours_spanning(start_utc, end_utc):
        try:
            hour = _fetch_hour(hk, is_current=(hk == cur_key))
        except Exception:
            continue                     # a missing/failed hour just contributes nothing (fallback covers gaps)
        for t, temp in hour.get(sid, []):
            if start_utc <= t < end_day:
                obs.append((t, temp))
    obs.sort()
    return obs


class MadisFeed:
    """Drop-in for kwx_runner.set_feed(). FREE MADIS hfmetar 5-min ASOS -> LST-day running max/min."""
    name = "madis-hfmetar-free"

    def running_extreme(self, station, lst_date, offset, kind):
        obs = _day_obs(station, lst_date, offset)
        if not obs:
            return None                  # no hfmetar for this station (e.g. hourly-only) -> caller falls back
        temps = [t for _, t in obs]
        return {"extreme_f": (max(temps) if kind == "max" else min(temps)),
                "obs": [(t.isoformat(), round(v, 2)) for t, v in obs]}


def probe(stations):
    """Measure per-station resolution + data latency from the current-hour file (the key freshness test)."""
    now = dt.datetime.now(tz=dt.timezone.utc)
    cur = now.strftime("%Y%m%d_%H00")
    hour = _fetch_hour(cur, is_current=True)
    print(f"current UTC {now.isoformat()}  (file {cur})")
    print(f"{'station':8}{'n_obs':>6}{'resolution(min)':>16}{'newest_utc':>22}{'data_age(min)':>15}")
    for s in stations:
        series = hour.get(_sid(s), [])
        if not series:
            print(f"{s:8}{'0':>6}   (no hfmetar -- hourly-only station; runner falls back to weather.gov)")
            continue
        sp = [(series[i][0] - series[i - 1][0]).total_seconds() / 60 for i in range(1, len(series))]
        res = sorted(sp)[len(sp) // 2] if sp else float("nan")
        newest = series[-1][0]
        print(f"{s:8}{len(series):>6}{res:>16.1f}{newest.strftime('%H:%M:%SZ'):>22}"
              f"{(now - newest).total_seconds() / 60:>15.1f}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "probe":
        probe(sys.argv[2].split(","))
    elif len(sys.argv) >= 4:
        st, date_s, off = sys.argv[1], sys.argv[2], float(sys.argv[3])
        feed = MadisFeed()
        for kind in ("max", "min"):
            r = feed.running_extreme(st, date_s, off, kind)
            print(f"{st} {date_s} LST running {kind}: "
                  f"{r['extreme_f']:.1f}F over {len(r['obs'])} obs" if r else f"{st} {date_s}: no obs")
    else:
        print("usage: madis_feed.py KMIA 2026-07-18 -5   |   madis_feed.py probe KMIA,KLAX,KDEN")
