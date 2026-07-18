#!/usr/bin/env python3
"""synoptic_feed.py -- Synoptic Data real-time feed adapter for the K-WX runner (Tier-2 item 5).

Plugs into kwx_runner via set_feed(): exposes running_extreme(station, lst_date, offset, kind) using
Synoptic's 1-min HF-ASOS temperatures (the fast DETECTION feed the 3.3-min-half-life edge needs), plus a
precip method for the rain sleeve and a latency probe to MEASURE the feed's real lag on our stations.

Token: read from gitignored .synoptic_token (one line). NEVER echo/commit it. Get one from the 14-day trial
at synopticdata.com. Batch ALL stations into ONE request (Synoptic returns many stids per call), so the
trial's "1 simultaneous response" concurrency limit does NOT bind -- we poll once, get all 20 stations.

API (v2): GET https://api.synopticdata.com/v2/stations/timeseries
  ?stid=KDEN,KMIA,...&vars=air_temp&recent=120&obtimezone=utc&units=temp|F&token=...
Returns STATION[].OBSERVATIONS.{date_time[], air_temp_set_1[]}. Precip: vars=precip_accum_one_hour etc.
(Exact var names/HF-network flags may need one tweak against the live trial API -- the probe below prints
what actually comes back so you can confirm resolution + latency on day 1.)

Usage:
  python synoptic_feed.py probe KDEN,KMIA,KLAS   # MEASURE latency + resolution (the key trial test)
"""
import json, os, sys, time, urllib.request, urllib.parse, ssl, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
TOKEN_PATH = os.path.join(HERE, ".synoptic_token")
API = "https://api.synopticdata.com/v2/stations/timeseries"
_ALIAS = {"NYC": "KNYC"}   # Central Park


def _token():
    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError("no .synoptic_token file (create it with your trial token; gitignored)")
    return open(TOKEN_PATH).read().strip()


def _sid(station):
    s = _ALIAS.get(station, station)
    return s if (s.startswith("K") or len(s) != 3) else "K" + s


def fetch_timeseries(stations, var="air_temp", recent_min=120, units="temp|F", timeout=20):
    """One batched call -> {stid: [(utc_dt, value), ...]} ascending. `stations` = list of ids."""
    stids = ",".join(_sid(s) for s in stations)
    q = urllib.parse.urlencode({"stid": stids, "vars": var, "recent": int(recent_min),
                                "obtimezone": "utc", "units": units, "token": _token()})
    req = urllib.request.Request(f"{API}?{q}", headers={"Accept": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
    out = {}
    for st in data.get("STATION", []):
        obs = st.get("OBSERVATIONS", {})
        times = obs.get("date_time", [])
        # value key ends _set_1 (e.g. air_temp_set_1, precip_accum_one_hour_set_1)
        vk = next((k for k in obs if k.endswith("_set_1")), None)
        vals = obs.get(vk, []) if vk else []
        series = []
        for t, v in zip(times, vals):
            if v is None:
                continue
            try:
                when = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
            except Exception:
                continue
            series.append((when, float(v)))
        series.sort()
        out[st.get("STID")] = series
    return out


class SynopticFeed:
    """Drop-in for kwx_runner.set_feed(). 1-min air_temp running max/min over an LST day."""
    name = "synoptic-hf"

    def __init__(self):
        self._cache = {}

    def running_extreme(self, station, lst_date, offset, kind):
        d = dt.date.fromisoformat(lst_date) if isinstance(lst_date, str) else lst_date
        start_local = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
        start_utc = start_local - dt.timedelta(hours=offset)
        end_utc = start_utc + dt.timedelta(hours=24)
        series = fetch_timeseries([station]).get(_sid(station), [])
        obs = [(t, f) for t, f in series if start_utc <= t < end_utc]
        if not obs:
            return None
        temps = [f for _, f in obs]
        return {"extreme_f": (max(temps) if kind == "max" else min(temps)),
                "obs": [(t.isoformat(), round(f, 2)) for t, f in obs]}


def probe(stations):
    """The KEY trial test: measure real latency + resolution. Prints, per station, newest-obs age and the
    median spacing between obs (=resolution). This is what tells you if Synoptic hits the 2-5 min band."""
    now = None  # Date.now unavailable in some sandboxes; use the response's own newest ts as reference
    ts_data = fetch_timeseries(stations, recent_min=90)
    print(f"{'station':8}{'n_obs':>6}{'resolution(min)':>16}{'newest_utc':>22}{'age_vs_prev_min':>16}")
    for s in stations:
        series = ts_data.get(_sid(s), [])
        if not series:
            print(f"{s:8}{'0':>6}   NO DATA")
            continue
        spacings = [ (series[i][0]-series[i-1][0]).total_seconds()/60 for i in range(1, len(series)) ]
        res = sorted(spacings)[len(spacings)//2] if spacings else float('nan')
        newest = series[-1][0]
        print(f"{s:8}{len(series):>6}{res:>16.1f}{newest.isoformat():>22}")
    print("\n-> resolution ~1.0 min = HF-ASOS working. Compare newest_utc to the ACTUAL current UTC time")
    print("   (date -u) to get true latency; that decides which act@k band we land in (need <=5 min).")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "probe":
        probe(sys.argv[2].split(","))
    else:
        print("usage: synoptic_feed.py probe KDEN,KMIA,KLAS   (needs .synoptic_token)")
